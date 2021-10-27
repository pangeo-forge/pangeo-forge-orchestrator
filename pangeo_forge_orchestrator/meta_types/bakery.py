from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

import fsspec
import yaml
from fsspec.registry import known_implementations
from pydantic import AnyUrl, BaseModel, constr, FilePath, HttpUrl
from pydantic.dataclasses import dataclass

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
s3_default_cache_types = Literal["bytes", "none"]

# turn fsspec's list of known_implementations into object which pydantic can validate against
KnownImplementations = Literal[tuple(list(known_implementations))]

FARGATE_CLUSTER = "aws.fargate"
AKS_CLUSTER = "azure.aks"
clusters = Literal[AKS_CLUSTER, FARGATE_CLUSTER]

PANGEO_FORGE_BAKERY_DATABASE = (
    "https://raw.githubusercontent.com/pangeo-forge/bakery-database/main/bakeries.yaml"
)
# ensure that secrets are passed as env var names enclosed in curly braces, e.g. `"{MY_AWS_KEY}"`
env_var_name = constr(regex=r"{(.*?)}")
# accepts only strings of integer values 0-9
run_identifier = constr(regex=r"^\d+$")
# see https://github.com/pangeo-forge/roadmap/pull/34; the "@" delimiter is introduced here
feedstock_name_with_version = constr(regex=r".*-feedstock@(0|[1-9]\d*)\.(0|[1-9]\d*)$")
# TODO: possibly move recipe name validation into `pangeo_forge_orchestrator.meta_types.meta`
# note that the string prior to the optional ":" delimiter must be a valid python identifier, but
# the string after ":" is a dictionary key, and therefore does not have this requirement
recipe_or_dictobj_identifier = constr(
    regex=r"^([A-Za-z][A-Za-z0-9_]*)([:][A-Za-z][A-Za-z0-9_-]*)?$"
)


class StorageOptions(BaseModel):
    key: Optional[env_var_name] = None
    secret: Optional[env_var_name] = None
    anon: Optional[bool] = None
    client_kwargs: Optional[dict] = None
    default_cache_type: Optional[s3_default_cache_types] = None
    default_fill_cache: Optional[bool] = None
    use_listings_cache: Optional[bool] = None

    class Config:
        extra = "forbid"


@dataclass
class Endpoint:
    protocol: KnownImplementations
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
    flow_storage_protocol: KnownImplementations
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


@dataclass
class BakeryName:
    name: str
    region: Optional[regions] = None
    organization_url: Optional[HttpUrl] = None

    def __post_init__(self):
        split = self.name.split(".bakery.")
        self.region = split[-1]
        reversed_url_list = split[0].split(".")
        self.organization_url = f"https://{'.'.join(reversed(reversed_url_list))}"


class BakeryDatabase(BaseModel):
    """A database of Pangeo Forge Bakeries.

    :param path: Path to local or remote YAML file with content conforming to ``BakeryMeta`` model.
    :param bakeries: The content of the YAML file to which ``path`` points.
    """

    path: Optional[Union[AnyUrl, FilePath]] = None  # Not optional, but assigned in __init__
    bakeries: Optional[dict] = None
    names: Optional[List[BakeryName]] = None

    class Config:
        validate_assignment = True  # validate `__init__` assignments, e.g. `self.path`
        arbitrary_types_allowed = True  # for `fsspec.AbstractFileSystem` in child model

    def __init__(self, path=PANGEO_FORGE_BAKERY_DATABASE):
        super().__init__()
        self.path = path
        with fsspec.open(self.path) as f:
            self.bakeries = yaml.safe_load(f.read())
        self.names = [BakeryName(name=name) for name in list(self.bakeries)]


@dataclass
class RunRecord:
    timestamp: datetime
    feedstock: feedstock_name_with_version
    recipe: recipe_or_dictobj_identifier
    path: str  # TODO: Define naming convention; cf. https://github.com/pangeo-forge/roadmap/pull/27


@dataclass
class BuildLogs:
    logs: Dict[run_identifier, RunRecord]
    run_ids: Optional[List[run_identifier]] = None

    def __post_init__(self):
        self.run_ids = list(self.logs)
