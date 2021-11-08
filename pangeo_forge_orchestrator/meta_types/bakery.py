from datetime import datetime
from typing import Dict, List, Literal, Optional, Union, get_args

from fsspec.registry import known_implementations
from pydantic import BaseModel, constr, validator
from pydantic.dataclasses import dataclass
from pydantic.networks import HttpUrl

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
KnownImplementations = Literal[tuple(list(known_implementations))]  # type: ignore

FARGATE_CLUSTER = "aws.fargate"
AKS_CLUSTER = "azure.aks"
clusters = Literal[FARGATE_CLUSTER, AKS_CLUSTER]  # type: ignore

# ensure that secrets are passed as env var names enclosed in curly braces, e.g. `"{MY_AWS_KEY}"`
env_var_name = constr(regex=r"{(.*?)}")
# see https://github.com/pangeo-forge/roadmap/pull/34; the "@" delimiter is introduced here
feedstock_name_with_version = constr(regex=r".*-feedstock@(0|[1-9]\d*)\.(0|[1-9]\d*)$")
# TODO: possibly move recipe name validation into `pangeo_forge_orchestrator.meta_types.meta`
# note that the string prior to the optional ":" delimiter must be a valid python identifier, but
# the string after ":" is a dictionary key, and therefore does not have this requirement
recipe_or_dictobj_identifier = constr(
    regex=r"^([A-Za-z][A-Za-z0-9_]*)([:][A-Za-z][A-Za-z0-9_-]*)?$"
)


class StorageOptions(BaseModel):
    key: Optional[env_var_name] = None  # type: ignore
    secret: Optional[env_var_name] = None  # type: ignore
    anon: Optional[bool] = None
    # TODO: ensure `v` in `{"client_kwargs": {"headers": {"Authorization": v}}}` is `env_var_name`?
    client_kwargs: Optional[dict] = None
    default_cache_type: Optional[s3_default_cache_types] = None
    default_fill_cache: Optional[bool] = None
    use_listings_cache: Optional[bool] = None
    username: Optional[env_var_name] = None  # type: ignore
    password: Optional[env_var_name] = None  # type: ignore

    class Config:
        extra = "forbid"


@dataclass(frozen=True)
class Endpoint:
    protocol: KnownImplementations  # type: ignore
    storage_options: Optional[StorageOptions] = None
    prefix: Optional[str] = None


@dataclass(frozen=True)
class Target:
    region: regions
    private: Optional[Endpoint] = None
    public: Optional[Endpoint] = None
    description: Optional[str] = None
    prefix: Optional[str] = None


@dataclass(frozen=True)
class FargateClusterOptions:
    vpc: str
    cluster_arn: str
    task_role_arn: str
    execution_role_arn: str
    security_groups: List[str]


@dataclass(frozen=True)
class Cluster:
    type: clusters  # type: ignore
    pangeo_forge_version: str
    pangeo_notebook_version: str
    prefect_version: str
    worker_image: str
    flow_storage: str
    flow_storage_protocol: KnownImplementations  # type: ignore
    flow_storage_options: StorageOptions
    max_workers: int
    cluster_options: Optional[FargateClusterOptions] = None


@dataclass(frozen=True)
class BakeryMeta:
    region: regions
    targets: Dict[str, Target]
    cluster: Union[Cluster, None]
    description: Optional[str] = None
    org_website: Optional[str] = None


@dataclass(frozen=True)
class BakeryName:
    name: str

    @validator("name")
    def name_must_match_spec(cls, v):

        split = v.split(".bakery.")
        region = split[-1]
        assert region in get_args(regions)

        class CheckHttpUrl(BaseModel):
            url: HttpUrl

        reversed_url_list = split[0].split(".")
        organization_url = f"https://{'.'.join(reversed(reversed_url_list))}"
        CheckHttpUrl(url=organization_url)

        return v


@dataclass(frozen=True)
class BakeryDatabase:
    bakeries: Dict[BakeryName, BakeryMeta]


def bakery_database_from_dict(d):
    d = {BakeryName(name=k): BakeryMeta(**v) for k, v in d.items()}
    return BakeryDatabase(bakeries=d)


@dataclass(frozen=True)
class RunRecord:
    timestamp: datetime
    feedstock: feedstock_name_with_version  # type: ignore
    recipe: recipe_or_dictobj_identifier  # type: ignore
    path: str  # TODO: Define naming convention; cf. https://github.com/pangeo-forge/roadmap/pull/27


@dataclass(frozen=True)
class BuildLogs:
    logs: Dict[int, RunRecord]

    @property
    def run_ids(self) -> List[int]:
        return list(self.logs)
