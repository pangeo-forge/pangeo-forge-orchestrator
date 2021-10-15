from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Union
from typing_extensions import TypedDict

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
    "azure.eastus",
    "azure.eastus2",
    "azure.southcentralus",
    "azure.westus2",
    "azure.westus3",
    "azure.australiaeast",
    "azure.southeastasia",
    "azure.northeurope",
    "azure.swedencentral",
    "azure.uksouth",
    "azure.westeurope",
    "azure.centralus",
    "azure.northcentralus",
    "azure.westus",
    "azure.southafricanorth",
    "azure.centralindia",
    "azure.eastasia",
    "azure.japaneast",
    "azure.jioindiawest",
    "azure.koreacentral",
    "azure.canadacentral",
    "azure.francecentral",
    "azure.germanywestcentral",
    "azure.norwayeast",
    "azure.switzerlandnorth",
    "azure.uaenorth",
    "azure.brazilsouth",
    "azure.centralusstage",
    "azure.eastusstage",
    "azure.eastus2stage",
    "azure.northcentralusstage",
    "azure.southcentralusstage",
    "azure.westusstage",
    "azure.westus2stage",
    "azure.asia",
    "azure.asiapacific",
    "azure.australia",
    "azure.brazil",
    "azure.canada",
    "azure.europe",
    "azure.global",
    "azure.india",
    "azure.japan",
    "azure.uk",
    "azure.unitedstates",
    "azure.eastasiastage",
    "azure.southeastasiastage",
    "azure.centraluseuap",
    "azure.eastus2euap",
    "azure.westcentralus",
    "azure.southafricawest",
    "azure.australiacentral",
    "azure.australiacentral2",
    "azure.australiasoutheast",
    "azure.japanwest",
    "azure.jioindiacentral",
    "azure.koreasouth",
    "azure.southindia",
    "azure.westindia",
    "azure.canadaeast",
    "azure.francesouth",
    "azure.germanynorth",
    "azure.norwaywest",
    "azure.swedensouth",
    "azure.switzerlandwest",
    "azure.ukwest",
    "azure.uaecentral",
    "azure.brazilsoutheast",
]

S3_PROTOCOL = "s3"
ABFS_PROTOCOL = "abfs"
protocols = Literal[ABFS_PROTOCOL, S3_PROTOCOL]

FARGATE_CLUSTER = "aws.fargate"
AKS_CLUSTER = "azure.aks"
clusters = Literal[AKS_CLUSTER, FARGATE_CLUSTER]


class StorageOptions(TypedDict, total=False):
    # Experimenting with this as a TypedDict, rather than a dataclass, because we don't want
    # arbitrary fields passed into fsspec instances as kwargs (in `components.Bakery`, e.g.)
    # Pydantic requires `typing_extensions.TypedDict`; `total=False` allows subsets of keys.
    key: str
    secret: str
    anon: bool
    client_kwargs: dict
    default_cache_type: str
    default_fill_cache: bool
    use_listings_cache: bool


@dataclass
class Endpoint:
    protocol: protocols
    storage_options: Optional[StorageOptions] = None
    prefix: Optional[str] = None


@dataclass
class Target:
    region: regions
    private: Optional[Endpoint] = None
    public: Optional[Endpoint] = None
    description: Optional[str] = None
    prefix: Optional[str] = None


@dataclass
class FargateClusterOptions:
    vpc: str
    cluster_arn: str
    task_role_arn: str
    execution_role_arn: str
    security_groups: List[str]


@dataclass
class Cluster:
    type: clusters
    pangeo_forge_version: str
    pangeo_notebook_version: str
    prefect_version: str
    worker_image: str
    flow_storage: str
    flow_storage_protocol: protocols
    flow_storage_options: StorageOptions
    max_workers: int
    cluster_options: Optional[FargateClusterOptions] = None


@dataclass
class BakeryMeta:
    region: regions
    targets: Dict[str, Target]
    cluster: Union[Cluster, None]
    description: Optional[str] = None
    org_website: Optional[str] = None
