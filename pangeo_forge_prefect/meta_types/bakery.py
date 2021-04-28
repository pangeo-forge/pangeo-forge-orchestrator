from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

regions = Literal[
    "aws.us-east-1",
    "aws.us-east-2",
    "aws.us-west-1",
    "aws.us-west-2",
    "aws.ca-central-1",
    "aws.eu-west-1",
    "aws.eu-central-1",
    "aws.eu-west-2",
    "aws.eu-west-3",
    "aws.eu-north-1",
    "aws.ap-northeast-1",
    "aws.ap-northeast-2",
    "aws.ap-southeast-1",
    "aws.ap-southeast-2",
    "aws.ap-south-1",
    "aws.sa-east-1",
    "aws.us-gov-west-1",
    "aws.us-gov-east-1",
]

S3_PROTOCOL = "s3"
FARGATE_CLUSTER = "aws.fargate"


@dataclass
class StorageOptions:
    key: Optional[str] = None
    secret: Optional[str] = None


@dataclass
class Endpoint:
    protocol: Literal[S3_PROTOCOL]
    storage_options: Optional[StorageOptions] = None
    prefix: Optional[str] = None


@dataclass
class Target:
    region: regions
    private: Optional[Endpoint] = None
    description: Optional[str] = None
    prefix: Optional[str] = None


@dataclass
class Cluster:
    type: Literal[FARGATE_CLUSTER]
    worker_image: str
    vpc: str
    cluster_arn: str
    task_role_arn: str
    execution_role_arn: str
    security_groups: List[str]
    flow_storage: str
    flow_storage_protocol: Literal[S3_PROTOCOL]
    flow_storage_options: StorageOptions
    max_workers: int


@dataclass
class Bakery:
    region: regions
    targets: Dict[str, Target]
    cluster: Cluster
    description: Optional[str] = None
    org_website: Optional[str] = None
