# AWS Billing Parser

This is a command-line tool for parsing an AWS billing CSV file and calculating total usage for EC2, Lambda, and Fargate. The results are written to an Excel file with two sheets: Detail and Total.

## Installation

To install the dependencies for this app using pipenv, run:

```bash
pipenv install
```

## Usage

To run the app, use the following command:

```bash
python main.py billing.csv --use-cache
```

This will parse the AWS billing CSV file and calculate total usage for EC2, Lambda, and Fargate. The billing.csv file should be in the same directory as main.py. The --use-cache flag is used to enable or disable use of the cache (default: enabled).

If you want to use the cache without providing AWS credentials, you can use the following command:

```bash
python main.py billing.csv --use-cache
```

If you want to use AWS credentials without using the cache, you can use the following command:

```bash
python main.py billing.csv --no-cache --access-key-id <ACCESS_KEY_ID> --secret-access-key <SECRET_ACCESS_KEY> --region <REGION>
```

Replace <ACCESS_KEY_ID>, <SECRET_ACCESS_KEY>, and <REGION> with your AWS access key ID, secret access key, and region, respectively. Note that the --no-cache flag is used to disable use of the cache in this example. If you want to enable the cache, remove this flag from the command.

## Generate AWS API keys

If you do not have an AWS access key ID and secret access key, you can generate them using the following steps:

1. Log in to the AWS Management Console.
2. Navigate to the IAM console.
3. Create a new IAM user with programmatic access.
4. Attach a policy to the user that grants the minimum required permissions for describe_instance_types API action. For example, the following policy grants read-only access to EC2 instance types in the us-west-2 region:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DescribeInstanceTypes",
      "Effect": "Allow",
      "Action": "ec2:DescribeInstanceTypes",
      "Resource": "*",
      "Condition": {
        "ForAnyValue:StringEquals": {
          "ec2:Region": "us-west-2"
        }
      }
    }
  ]
}
```

After creating the user, save the access key ID and secret access key.
