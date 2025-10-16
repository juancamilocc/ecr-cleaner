# Manage ECR Images

## Description

`ecr-cleaner` is a small Python utility to manage images stored in Amazon ECR (Elastic Container Registry). The script lists images from an ECR repository, validates and parses tags that follow a specific convention, groups images by project/client/environment, and deletes older versions while keeping a configurable number of recent versions per group.

----

## Purpose and problem solved

The ECR repositories can quickly accumulate many old image tags. That leads to wasted storage and a cluttered registry. This tool automates cleaning by keeping only the latest N versions per variant (for example `prod`, `staging`, different clients) and provides a dry-run mode so you can review deletions before executing them.

Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`
- AWS credentials with `ecr:DescribeImages`, `ecr:ListImages` and `ecr:BatchDeleteImage` permissions for the target repository

### Configuration

Define your pattern. By default is the next one: [Default Pattern](http://)

```python
full_pattern_image_tag = re.compile(
        # Define your pattern here by regular expressions!!!
    )
```

Create a `policy.json` file with the next content.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecr:DescribeImages",
                "ecr:BatchDeleteImage",
                "ecr:ListImages"
            ],
            "Resource": "arn:aws:ecr:<your-aws-region>:<your-aws-id>:<your-ecr-repository-name>" // Change this according your ecr
        }
    ]
}
```

Create IAM policy, role and service account based on policy.

```bash
aws iam create-policy \
    --policy-name ECRCleanerPolicy \
    --policy-document file://policy.json

eksctl create iamserviceaccount \
    --name ecr-cleaner-sa \
    --namespace default \
    --cluster <your-eks-name> \
    --attach-policy-arn arn:aws:iam::<your-aws-id>:policy/ECRCleanerPolicy \
    --approve
```

Build and push docker image.

```bash
docker build --no-cache -t <your-aws-id>.dkr.ecr.<your-aws-region>.amazonaws.com/<your-ecr-repository-name>:ecr-cleaner .
docker push <your-aws-id>.dkr.ecr.<your-aws-region>.amazonaws.com/<your-ecr-repository-name>:ecr-cleaner
```

Create a cron job.

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ecr-cleaner
  namespace: default
spec:
  schedule: "0 23 * * *" # Change this according to your needs
  jobTemplate:
    spec:
      ttlSecondsAfterFinished: 10
      template:
        spec:
          serviceAccountName: ecr-cleaner-sa
          containers:
          - name: ecr-cleaner-job
            image: <your-aws-id>.dkr.ecr.<your-aws-region>.amazonaws.com/<your-ecr-repository-name>:ecr-cleaner # Change this according your ecr
            args:
              - "--repository_name" 
              - "<ECR-repository-name>" # Change this according your ecr
              - "--region" 
              - "<your-aws-region>"     # Change this according your region
              - "--execute"
          restartPolicy: OnFailure
```

**Note:** You can also change the number of images to keep, including it in the args by `--keep-versions`. By default its value is `3`.

Apply the cronjob on cluster.

```bash
kubectl apply -f cronjob-ecr-cleaner.yaml
```

----

## Usage

Dry-run (default):

```bash
python main.py --repository_name <ECR-repository-name> --region <your-aws-region> --keep-versions 3
```

Execute deletion:

```bash
python main.py --repository_name <ECR-repository-name> --region <your-aws-region> --keep-versions 3 --execute
```

### Main arguments

- `--repository_name`: ECR repository name.
- `--region`: AWS region.
- `--keep-versions`: Number of versions to keep per group (default: `3`).
- `--execute`: Flag to actually perform deletion (if omitted, script runs in dry-run).

### Best practices

- Always run in dry-run mode first to review what will be deleted.
- Verify internal policies and approvals before deleting images in production.
- Use IAM roles with least privilege.
