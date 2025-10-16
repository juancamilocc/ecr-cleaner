import logging, boto3, re, argparse
from datetime import datetime
from itertools import groupby
from typing import Tuple, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def get_all_images(ecr_client: Any, repository_name: str) -> list:
    """
    Retrieve all images from ECR.

    Input:
        - repository_name: The name of the ECR repository to retrieve images from.
        - region: The AWS region where the ECR repository is located.

    Output:
        - A list of image details (e.g., image tags) from the specified ECR repository.
    """
    paginator = ecr_client.get_paginator("list_images")
    images = []
    
    pagination_params = {
        'repositoryName': repository_name
    }

    logger.info(f"Retrieving images from {repository_name} ECR...")
    try:
        for page in paginator.paginate(**pagination_params):
            images.extend(page.get("imageIds", []))
    except ecr_client.exceptions.RepositoryNotFoundException as e:
        logger.error(f"Repository not found in ECR: {e}")

    logger.info(f"Retrieved {len(images)} images from {repository_name} ECR.")
    return images

def get_validated_images(images: list) -> dict:
    """
    Validate image tags and extract relevant metadata.

    Input:
        - images: A list of image details retrieved from ECR.

    Output: 
        - A list of validated image metadata dictionaries.
    """
    validated_images = []
    for image_detail in images:
        digest = image_detail.get('imageDigest')
        
        if not digest:
            continue

        image_tag = image_detail.get("imageTag")
        parsed_data = parse_image_tag(image_tag)

        if parsed_data:
            parsed_data['imageDigest'] = digest
            validated_images.append(parsed_data)
        else:
            logger.debug(f"Tag: '{image_tag}' - Ignored (invalid format or missing hash)")

    return validated_images

def parse_image_tag(image_tag: str) -> dict | None:
    """
    Retrieve structured information from an image tag filtering by regular expression.
    Adapted to the following syntax: {project_name}-{project_hash}-{project_date}-{project_client}-{project_environment}

    Input:
        - image_tag: The image tag to parse and extract information from.

    Output:
        - A dictionary containing the parsed information from the image tag, or None if the tag is invalid.
    """

    full_pattern_image_tag = re.compile(
        r"^(?P<project_name>.+?)-"                                  # Project Name
        r"(?P<project_hash>[a-f0-9]{7})-"                           # Project Hash
        r"(?P<project_date>\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})"    # Project Date, like %Y-%m-%d-%H-%M-%S
        r"(?:-(?P<project_client>.+?))?-"                           # Project Client (Optional)
        r"(?P<project_environment>[a-zA-Z]+)$"                      # Project Environment
    )
    
    match = full_pattern_image_tag.match(image_tag)

    if match:
        data = match.groupdict()

        return {
            "project_name": data.get('project_name'),
            "project_hash": data.get('project_hash'),
            "project_date": datetime.strptime(data.get('project_date'), "%Y-%m-%d-%H-%M-%S"),
            "project_client": data.get('project_client') or 'N/A',
            "project_environment": data.get('project_environment')
        }
    
    else:
        logger.warning(f"Tag: '{image_tag}' - Ignored (invalid format or missing hash)")
        return None

def get_digests_by_status(validated_images: dict, keep_versions: int) -> Tuple[set, set]:
    """
    Retrieve the sets of image digests to keep and delete based on their status.

    Input:
        - valid_tagged_images: A list of valid tagged images with their metadata.

    Output:
        - A tuple containing two sets: digests_to_keep and digests_to_delete.
    """
    group_key = lambda image: (image['project_environment'], image['project_client'], image['project_name'])
    validated_images.sort(key=group_key)

    digests_to_keep = set()
    digests_to_delete = set()

    for key, group in groupby(validated_images, key=group_key):
        group_list = list(group)

        group_list.sort(key=lambda image: image['project_date'], reverse=True)
        images_to_keep = group_list[:keep_versions]
        images_to_delete = group_list[keep_versions:]

        logging.info(
            f"Group: {key} | Total: {len(group_list)} | To keep: {len(images_to_keep)} | To delete: {len(images_to_delete)}"
        )

        for image in images_to_keep:
            digests_to_keep.add(image['imageDigest'])
        for image in images_to_delete:
            digests_to_delete.add(image['imageDigest'])

    final_digests_to_delete = digests_to_delete - digests_to_keep
    return digests_to_keep, final_digests_to_delete

def delete_images(ecr_client: Any, final_digests_to_delete: set, args: Any):
    """
    Delete images from ECR repository.

    Input:
        - final_digests_to_delete: A set of image digests to delete.
        - args: The command-line arguments.
    """
    if not final_digests_to_delete:
        logger.info("No images to delete.")
        return

    logger.info(f"Total images to delete: {len(final_digests_to_delete)}")

    if args.execute:
        logger.warning("--- Execution Mode ---")
        image_ids_to_delete = [{'imageDigest': digest} for digest in final_digests_to_delete]

        # Delete with chunks of 100
        for i in range(0, len(image_ids_to_delete), 100):
            chunk = image_ids_to_delete[i:i+100]
            try:
                response = ecr_client.batch_delete_image(
                    repositoryName=args.repository_name,
                    imageIds=chunk
                )
                logger.info(f"Successfully deleted a batch of {len(response.get('imageIds', []))} images.")
                
                if response.get('failures'):
                    logger.error(f"Failures: {response['failures']}")
            except Exception as e:
                logger.error(f"Error deleting image batch: {e}")
    else:
        logger.warning("--- Simulation Mode (Dry Run) ---")
        logger.info("The following image digests would be deleted:")
        
        for digest in final_digests_to_delete:
            print(f"  - {digest}")
        logger.warning("To execute deletion, run the script with the --execute flag.")

def main(args):

    ecr_client = boto3.client(
        "ecr", region_name=args.region, 
        config=boto3.session.Config(retries={"max_attempts": 10})
    )

    images = get_all_images(ecr_client, args.repository_name)
    validated_images = get_validated_images(images)
    _, images_to_delete = get_digests_by_status(validated_images, args.keep_versions)
    delete_images(ecr_client, images_to_delete, args)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage ECR images based on syntax: {project_name}-{project_hash}-{project_date}-{project_client}-{project_environment}")
    parser.add_argument("--repository_name", help="The name of the ECR repository to manage images from.")
    parser.add_argument("--region", help="The AWS region where the ECR repository is located.")
    parser.add_argument("--keep-versions", type=int, default=3, help="Number of recent versions to keep per group.")
    parser.add_argument("--execute", action="store_true", help="Flag to actually delete images. Default is dry run.")

    cli_args = parser.parse_args()
    main(cli_args)