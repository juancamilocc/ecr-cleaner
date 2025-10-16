import unittest
from datetime import datetime

from main import parse_image_tag, get_digests_by_status


class TestMain(unittest.TestCase):
    
    def test_parse_image_tag_valid_with_client(self):
        tag = "myproj-1a2b3c4-2025-09-25-15-30-00-clientA-prod"
        parsed = parse_image_tag(tag)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["project_name"], "myproj")
        self.assertEqual(parsed["project_hash"], "1a2b3c4")
        self.assertEqual(parsed["project_date"], datetime(2025, 9, 25, 15, 30, 0))
        self.assertEqual(parsed["project_client"], "clientA")
        self.assertEqual(parsed["project_environment"], "prod")

    def test_parse_image_tag_valid_without_client(self):
        tag = "service-abcdef1-2022-01-01-00-00-00-staging"
        parsed = parse_image_tag(tag)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["project_name"], "service")
        self.assertEqual(parsed["project_hash"], "abcdef1")
        self.assertEqual(parsed["project_date"], datetime(2022, 1, 1, 0, 0, 0))
        self.assertEqual(parsed["project_client"], "N/A")
        self.assertEqual(parsed["project_environment"], "staging")

    def test_parse_image_tag_invalid(self):
        tag = "badformat-2025-09-25-15-30-00-client-prod"
        parsed = parse_image_tag(tag)
        self.assertIsNone(parsed)

    def make_image(self, project_name, hash_, date_str, client, env, digest):
        parsed = parse_image_tag(f"{project_name}-{hash_}-{date_str}-{client}-{env}")
        self.assertIsNotNone(parsed)
        parsed['imageDigest'] = digest
        return parsed

    def test_get_digests_by_status_grouping_and_retention(self):
        imgs = [
            self.make_image('proj', 'aaaaaaa', '2025-01-05-00-00-00', 'C', 'prod', 'd5'),
            self.make_image('proj', 'bbbbbbb', '2025-01-04-00-00-00', 'C', 'prod', 'd4'),
            self.make_image('proj', 'ccccccc', '2025-01-03-00-00-00', 'C', 'prod', 'd3'),
            self.make_image('proj', 'ddddddd', '2025-01-02-00-00-00', 'C', 'prod', 'd2'),
            self.make_image('proj', 'eeeeeee', '2025-01-01-00-00-00', 'C', 'prod', 'd1'),
        ]

        keep, delete = get_digests_by_status(imgs, keep_versions=2)
        self.assertEqual(keep, {'d5', 'd4'})
        self.assertEqual(delete, {'d3', 'd2', 'd1'})


if __name__ == '__main__':
    unittest.main()
