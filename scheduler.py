#!/usr/bin/env python

import os
import time
import random
import yaml
import json
import logging
import logging.config
from kubernetes import client, config, watch


config.load_incluster_config()
# config.load_kube_config()
v1 = client.CoreV1Api()


svc_config_file = os.getenv("SCHEDULER_CONFIG")
with open(svc_config_file, "r") as f:
    cfg = yaml.safe_load(f.read())
    SCHEDULER_NAME = cfg["schedulerName"]
    SELECTION_CRITERIA = cfg["selectionCriteria"]


log_config_file = os.getenv("SCHEDULER_LOGGING_CONFIG")
with open(log_config_file, "r") as f:
    log_cfg = yaml.safe_load(f.read())
    logging.config.dictConfig(log_cfg)
    LOGGER = logging.getLogger("stdout")


def node_finder(node_labels):

    # Does the node match the criteria
    # kalamajakapital.ee/min-containerd-version
    # kalamajakapital.ee/min-kubelet-version
    # kalamajakapital.ee/no-sensitive-mount

    for label, value in SELECTION_CRITERIA.items():
        try:
            label_value = node_labels[label]
            if label_value in SELECTION_CRITERIA[label]:
                logging.debug(
                    f"{label} value of {label_value} meets the criteria: {SELECTION_CRITERIA[label]}"
                )
            else:
                logging.warning(
                    f"{label} value of {label_value} doesn't meet the criteria: {SELECTION_CRITERIA[label]}"
                )
                return
        except KeyError:
            logging.warning(f"Label {label} doesn't exist for given node.")
            # Break the function, the node doesn't have a mandatory label.
            return
    # Do the nodes already have sensitive mounts.
    return True


def nodes_available():
    ready_nodes = []
    for node in v1.list_node().items:
        logging.info(f"available node {node}")
        for status in node.status.conditions:
            if status.status == "True" and status.type == "Ready":
                node_meets_criteria = node_finder(node.metadata.labels)
                if node_meets_criteria:
                    ready_nodes.append(node.metadata.name)
    return ready_nodes


def scheduler(name, namespace, node):

    meta = client.V1ObjectMeta()
    meta.name = name

    target = client.V1ObjectReference()
    target.kind = "Node"
    target.apiVersion = "v1"
    target.name = node
    body = client.V1Binding(target=target, metadata=meta)
    # TODO: handle the condition..
    # 2021-11-01 19:22:18,614 [ERROR] Operation cannot be fulfilled on pods/binding "foobar-sched-b795dd5cb-m2xpb": pod foobar-sched-b795dd5cb-m2xpb is already assigned to node "pool-tiny-0xpxld6s7-3dj4j"
    return v1.create_namespaced_pod_binding(
        name, namespace, body, _preload_content=False
    )


def process_event(event):

    phase = event["object"].status.phase
    required_scheduler = event["object"].spec.scheduler_name
    pod_name = event["object"].metadata.name
    namespace = event["object"].metadata.namespace

    if phase == "Pending" and required_scheduler == SCHEDULER_NAME:
        meta = {
            "pod_name": pod_name,
            "nodes_available": nodes_available(),
        }
        try:
            logging.info(f"{phase} pod with {required_scheduler} scheduler.", extra=meta)
            if meta["nodes_available"]:
                res = scheduler(
                    pod_name, namespace, random.choice(meta["nodes_available"])
                )
                logging.debug(res)
            else:
                logging.warning(f"no nodes available for scheduling.", extra=meta)
        except client.rest.ApiException as e:
            logging.error(json.loads(e.body)["message"], extra=meta)


def run():
    w = watch.Watch()
    logging.info("watching events")

    # TODO: remember events where pod couldn't be scheduled, and try again later.
    for event in w.stream(v1.list_pod_for_all_namespaces):
        process_event(event)

    logging.info("finished watching events")


if __name__ == "__main__":
    run()
