#!/usr/bin/env python
"""
Adapted from https://github.com/yuvipanda/mybinder-analytics/blob/main/logs.py

Note: this should be moved in pangeo-forge-runner, xref:
  https://github.com/pangeo-forge/pangeo-forge-runner/issues/20

Putting it here for now because that seems like a more efficient path to getting
this essential functionality deployed.
"""
import argparse
import asyncio
import json
import subprocess
import sys
import time
import typing
from datetime import datetime
from typing import Union

from dateutil.parser import isoparse, parse as dateparse  # type: ignore


class LogRecord(typing.NamedTuple):
    """
    Structured log entry coming out of dataflow.
    """

    timestamp: datetime
    source: str
    message: str
    instance: str

    def __str__(self):
        out = f"[{self.timestamp.isoformat()}] [{self.source}"
        if self.instance:
            out += f":{self.instance}"
        out += f"] {self.message}"
        return out


class DataFlowJob(typing.NamedTuple):
    """
    Representation of a data flow job
    """

    id: str
    creation_time: datetime
    location: str
    name: str
    state: str
    state_time: datetime
    type: str


async def get_job(name: str) -> Union[DataFlowJob, None]:
    """
    Return job information for job with given dataflow name.

    Returns None if no such job is present
    """
    cmd = [
        "gcloud",
        "dataflow",
        "jobs",
        "list",
        f"--filter=name={name}",
        "--format=json",
    ]
    proc = await asyncio.subprocess.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    jobs = json.loads(stdout.decode())
    if jobs:
        job = jobs[0]
        return DataFlowJob(
            id=job["id"],
            creation_time=dateparse(job["creationTime"]),
            location=job["location"],
            name=job["name"],
            state=job["state"],
            state_time=dateparse(job["stateTime"]),
            type=job["type"],
        )
    return None


async def get_job_logs(
    job_id,
    source_filter: typing.List,
    instance_filter: typing.List,
    since: datetime = None,
):
    """
    Get logs for given job from given project.

    job_id:
        ID (not name) of the dataflow job we are looking for logs of
    source_filter:
        list of sources we want logs from. Allowed options are:

            - job-message: Messages from dataflow itself
            - docker: Logs from the docker containers running our workers in dataflow
            - system: Logs from the VMs running our workers
            - worker: Logs from the workers themselves, sometimes overlaps with messages from docker
            - kubelet: Logs from the kubelet on the VMs, responsible for starting up containers
            - agent: Not sure?
            - harness-startup: Not sure?
            - harness: Not sure?
            - shuffler-startup: Not sure?
            - shuffler: Not sure?
            - vm-health: Not sure?
            - vm-monitor: Not sure?
            - resource: Not sure?
            - insights: Not sure?
        Any combination of these can be provided, and logs from all these sources will be returned
    instance_filter:
        list of instance (VM) names we want logs from
    since:
        Show logs only after this timestamp
    """
    query = [f'resource.labels.job_id="{job_id}"']
    if source_filter:
        query.append(
            "("
            + " OR ".join(f'log_id("dataflow.googleapis.com/{sf}")' for sf in source_filter)
            + ")"
        )

    if instance_filter:
        query.append('labels."compute.googleapis.com/resource_type"="instance"')
        query.append(
            'labels."compute.googleapis.com/resource_name" = (' + " OR ".join(instance_filter) + ")"
        )
    if since:
        query.append(f'timestamp>"{since.isoformat()}"')
    cmd = [
        "gcloud",
        "logging",
        "read",
        "\n".join(query),
        "--format=json",
        "--order=asc",
    ]
    proc = await asyncio.subprocess.create_subprocess_exec(*cmd, stdout=subprocess.PIPE)
    stdout, _ = await proc.communicate()
    logs = json.loads(stdout.decode())

    for logline in logs:  # type: ignore
        timestamp = isoparse(logline["timestamp"])

        # logType looks like projects/<project-id>/logs/dataflow.googleapis.com%2F<type>
        # And type is what we ultimately care about
        source = logline["logName"].rsplit("%2F", 1)[-1]

        # Each log type should be handled differently
        if source in (
            "kubelet",
            "shuffler",
            "harness",
            "harness-startup",
            "vm-health",
            "vm-monitor",
            "resource",
            "agent",
            "docker",
            "system",
            "shuffler-startup",
            "worker",
        ):
            message = logline["jsonPayload"]["message"]
        elif source in ("job-message"):
            message = logline["textPayload"]
        elif source in ("insights",):
            # Let's ignore these
            continue
        else:
            print(source)
            print(logline)
            sys.exit(1)
        if logline["labels"].get("compute.googleapis.com/resource_type") == "instance":
            instance = logline["labels"]["compute.googleapis.com/resource_name"]
        else:
            instance = None
        # Trim additional newlines to prevent excess blank lines
        yield LogRecord(timestamp, source, message.rstrip(), instance)


async def main():
    argparser = argparse.ArgumentParser()

    argparser.add_argument("name")

    argparser.add_argument("--source", action="append")
    argparser.add_argument("--instance", action="append")
    argparser.add_argument("--follow", "-f", action="store_true")

    args = argparser.parse_args()

    job = await get_job(args.name)
    last_ts = None

    while True:
        newest_ts = None
        async for log in get_job_logs(job.id, args.source, args.instance, last_ts):
            newest_ts = log.timestamp
            print(log)
        if not args.follow:
            break
        if last_ts is None and newest_ts is not None:
            last_ts = newest_ts

        time.sleep(5)


asyncio.run(main())
