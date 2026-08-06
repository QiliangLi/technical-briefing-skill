# Set up the multi-cluster GKE Inference Gateway  |  GKE networking  |  Google Cloud Documentation

Source: https://docs.cloud.google.com/kubernetes-engine/docs/how-to/setup-multicluster-inference-gateway

- Home

- Documentation

- Application hosting

- Google Kubernetes Engine (GKE)

- GKE networking

- Guides

# Set up the multi-cluster GKE Inference Gateway Stay organized with collections Save and categorize content based on your preferences.

This document describes how to set up the multi-cluster Google Kubernetes Engine (GKE)
Inference Gateway to intelligently load-balance
your AI/ML inference workloads across multiple GKE clusters,
which can span different regions. This setup uses Gateway API, Multi Cluster Ingress, and
custom resources like InferencePool and InferenceObjective to help improve
scalability, help ensure high availability, and optimize resource utilization for
your model-serving deployments.

To understand this document, be familiar with the following:

- AI/ML orchestration on
GKE .

- Generative AI terminology .

- GKE networking
concepts , including: Services GKE Multi Cluster Ingress Gateway API

- Services

- GKE Multi Cluster Ingress

- Gateway API

- Load balancing in
Google Cloud , especially
how load balancers interact with GKE.

This document is for the following personas:

- Machine learning (ML) engineers, Platform admins and operators, or
Data and AI specialists who want to use GKE's container
orchestration capabilities for serving AI/ML workloads.

- Cloud architects or Networking specialists who interact with
GKE networking.

To learn more about common roles and example tasks referenced in
Google Cloud content, see Common GKE Enterprise user roles and
tasks .

## Before you begin

Before you start, make sure that you have performed the following tasks:

- Enable
    
    
    
    
    
    the Google Kubernetes Engine API.

- To use the Google Cloud CLI for this task, install and then initialize the
    gcloud CLI. If you previously installed the gcloud CLI, get the latest
    version by running the gcloud components update command. Earlier gcloud CLI versions might not support running the commands in this document.

- Enable the Compute Engine API, Kubernetes Engine API, Model Armor, and the Network Services API. Go to Enable access to
APIs and follow the instructions.

Enable the Compute Engine API, Kubernetes Engine API, Model Armor, and the Network Services API.

Go to Enable access to
APIs and follow the instructions.

- Enable the Autoscaling API. Go to Autoscaling
API and follow the instructions.

Enable the Autoscaling API.

Go to Autoscaling
API and follow the instructions.

- Enable the GKE Hub API. Go to GKE Hub
API and follow the instructions. Alternatively, use the Google Cloud CLI: gcloud services enable gkehub.googleapis.com --project = PROJECT_ID

Enable the GKE Hub API.

Go to GKE Hub
API and follow the instructions.

Alternatively, use the Google Cloud CLI:

gcloud services enable gkehub.googleapis.com --project = PROJECT_ID

- Hugging Face prerequisites: Create a Hugging Face account if you don't already have one. Request and get approval for access to the Qwen3-32B model on Hugging Face. Sign the license consent agreement on the model's page on Hugging Face. Generate a Hugging Face access token with at least Read permissions.

Hugging Face prerequisites:

- Create a Hugging Face account if you don't already have one.

- Request and get approval for access to the Qwen3-32B model on Hugging Face.

- Sign the license consent agreement on the model's page on Hugging Face.

- Generate a Hugging Face access token with at least Read permissions.

## Requirements

- Ensure your project has sufficient quota for H100 GPUs. For more
information, see Plan GPU quota and Allocation
quotas .

- Use GKE version 1.34.1-gke.1127000 or later.

- Use gcloud CLI version 480.0.0 or later.

- Your node service accounts must have permissions to write
metrics to the Autoscaling API.

- You must have the following IAM roles on the project: roles/container.admin and roles/iam.serviceAccountAdmin .

- All clusters that you register to the fleet, including the config cluster,
must be in the same VPC network. Multi-cluster Gateways don't
support load balancing across clusters in different VPC
networks.

### Multiport and NEG limits

When deploying multi-port InferencePool resources in a multi-cluster setup,
consider the Google Cloud Backend Service NEG limit. Each port in each zone
creates a dedicated NEG. For example, a regional cluster with three zones and
an InferencePool configured with eight ports will utilize 24 NEGs. Because a
Backend Service is limited to 50 NEGs, you can only aggregate this specific
InferencePool from a maximum of two clusters before reaching the limit.

## Set up multi-cluster Inference Gateway

To set up the multi-cluster GKE Inference Gateway, follow these steps:

### Create clusters and node pools

To host your AI/ML inference workloads and enable cross-regional load balancing,
create two GKE clusters in different regions, each with an H100
GPU node pool.

- Create the first cluster: gcloud container clusters create CLUSTER_1_NAME \ --region LOCATION \ --project = PROJECT_ID \ --gateway-api = standard \ --release-channel "rapid" \ --cluster-version = GKE_VERSION \ --machine-type = " MACHINE_TYPE " \ --disk-type = " DISK_TYPE " \ --enable-managed-prometheus --monitoring = SYSTEM,DCGM \ --hpa-profile = performance \ --async # Allows the command to return immediately Replace the following: CLUSTER_1_NAME : the name of the first cluster,
for example gke-west . LOCATION : the region for the first cluster,
for example europe-west3 . PROJECT_ID : your project ID. GKE_VERSION : the GKE version to
use, for example 1.34.1-gke.1127000 . MACHINE_TYPE : the machine type for the cluster
nodes, for example c2-standard-16 . DISK_TYPE : the disk type for the cluster nodes,
for example pd-standard .

Create the first cluster:

gcloud container clusters create CLUSTER_1_NAME \ --region LOCATION \ --project = PROJECT_ID \ --gateway-api = standard \ --release-channel "rapid" \ --cluster-version = GKE_VERSION \ --machine-type = " MACHINE_TYPE " \ --disk-type = " DISK_TYPE " \ --enable-managed-prometheus --monitoring = SYSTEM,DCGM \ --hpa-profile = performance \ --async # Allows the command to return immediately

Replace the following:

- CLUSTER_1_NAME : the name of the first cluster,
for example gke-west .

- LOCATION : the region for the first cluster,
for example europe-west3 .

- PROJECT_ID : your project ID.

- GKE_VERSION : the GKE version to
use, for example 1.34.1-gke.1127000 .

- MACHINE_TYPE : the machine type for the cluster
nodes, for example c2-standard-16 .

- DISK_TYPE : the disk type for the cluster nodes,
for example pd-standard .

- Create an H100 node pool for the first cluster: gcloud container node-pools create NODE_POOL_NAME \ --accelerator "type=nvidia-h100-80gb,count=2,gpu-driver-version=latest" \ --project = PROJECT_ID \ --location = CLUSTER_1_ZONE \ --node-locations = CLUSTER_1_ZONE \ --cluster = CLUSTER_1_NAME \ --machine-type = NODE_POOL_MACHINE_TYPE \ --num-nodes = NUM_NODES \ --spot \ --async # Allows the command to return immediately Replace the following: NODE_POOL_NAME : the name of the node pool,
for example h100 . PROJECT_ID : your project ID. CLUSTER_1_ZONE : the zone for the first cluster,
for example europe-west3-c . CLUSTER_1_NAME : the name of the first cluster,
for example gke-west . NODE_POOL_MACHINE_TYPE : the machine type for the
node pool, for example a3-highgpu-2g . NUM_NODES : the number of nodes in the node pool,
for example 3 .

Create an H100 node pool for the first cluster:

gcloud container node-pools create NODE_POOL_NAME \ --accelerator "type=nvidia-h100-80gb,count=2,gpu-driver-version=latest" \ --project = PROJECT_ID \ --location = CLUSTER_1_ZONE \ --node-locations = CLUSTER_1_ZONE \ --cluster = CLUSTER_1_NAME \ --machine-type = NODE_POOL_MACHINE_TYPE \ --num-nodes = NUM_NODES \ --spot \ --async # Allows the command to return immediately

Replace the following:

- NODE_POOL_NAME : the name of the node pool,
for example h100 .

- PROJECT_ID : your project ID.

- CLUSTER_1_ZONE : the zone for the first cluster,
for example europe-west3-c .

- CLUSTER_1_NAME : the name of the first cluster,
for example gke-west .

- NODE_POOL_MACHINE_TYPE : the machine type for the
node pool, for example a3-highgpu-2g .

- NUM_NODES : the number of nodes in the node pool,
for example 3 .

- Get the credentials: gcloud container clusters get-credentials CLUSTER_1_NAME \ --location CLUSTER_1_ZONE \ --project = PROJECT_ID Replace the following: PROJECT_ID : your project ID. CLUSTER_1_NAME : the name of the first cluster,
for example gke-west . CLUSTER_1_ZONE : the zone for the first cluster,
for example europe-west3-c .

Get the credentials:

gcloud container clusters get-credentials CLUSTER_1_NAME \ --location CLUSTER_1_ZONE \ --project = PROJECT_ID

Replace the following:

- PROJECT_ID : your project ID.

- CLUSTER_1_NAME : the name of the first cluster,
for example gke-west .

- CLUSTER_1_ZONE : the zone for the first cluster,
for example europe-west3-c .

- On the first cluster, create a secret for the Hugging Face token: kubectl create secret generic hf-token \ --from-literal = token = HF_TOKEN Replace the HF_TOKEN : your Hugging Face access token.

On the first cluster, create a secret for the Hugging Face token:

kubectl create secret generic hf-token \ --from-literal = token = HF_TOKEN

Replace the HF_TOKEN : your Hugging Face access token.

- Create the second cluster in a different region from the first cluster: gcloud container clusters create gke-east --region LOCATION \ --project = PROJECT_ID \ --gateway-api = standard \ --release-channel "rapid" \ --cluster-version = GKE_VERSION \ --machine-type = " MACHINE_TYPE " \ --disk-type = " DISK_TYPE " \ --enable-managed-prometheus \ --monitoring = SYSTEM,DCGM \ --hpa-profile = performance \ --async # Allows the command to return immediately while the cluster is created in the background. Replace the following: LOCATION : the region for the second cluster.
This must be a different region than the first cluster. For example, us-east4 . PROJECT_ID : your project ID. GKE_VERSION : the GKE version to
use, for example 1.34.1-gke.1127000 . MACHINE_TYPE : the machine type for the cluster
nodes, for example c2-standard-16 . DISK_TYPE : the disk type for the cluster nodes,
for example pd-standard .

Create the second cluster in a different region from the first cluster:

gcloud container clusters create gke-east --region LOCATION \ --project = PROJECT_ID \ --gateway-api = standard \ --release-channel "rapid" \ --cluster-version = GKE_VERSION \ --machine-type = " MACHINE_TYPE " \ --disk-type = " DISK_TYPE " \ --enable-managed-prometheus \ --monitoring = SYSTEM,DCGM \ --hpa-profile = performance \ --async # Allows the command to return immediately while the cluster is created in the background.

Replace the following:

- LOCATION : the region for the second cluster.
This must be a different region than the first cluster. For example, us-east4 .

- PROJECT_ID : your project ID.

- GKE_VERSION : the GKE version to
use, for example 1.34.1-gke.1127000 .

- MACHINE_TYPE : the machine type for the cluster
nodes, for example c2-standard-16 .

- DISK_TYPE : the disk type for the cluster nodes,
for example pd-standard .

- Create an H100 node pool for the second cluster: gcloud container node-pools create h100 \ --accelerator "type=nvidia-h100-80gb,count=2,gpu-driver-version=latest" \ --project = PROJECT_ID \ --location = CLUSTER_2_ZONE \ --node-locations = CLUSTER_2_ZONE \ --cluster = CLUSTER_2_NAME \ --machine-type = NODE_POOL_MACHINE_TYPE \ --num-nodes = NUM_NODES \ --spot \ --async # Allows the command to return immediately Replace the following: PROJECT_ID : your project ID. CLUSTER_2_ZONE : the zone for the second cluster,
for example us-east4-a . CLUSTER_2_NAME : the name of the second cluster,
for example gke-east . NODE_POOL_MACHINE_TYPE : the machine type for the
node pool, for example a3-highgpu-2g . NUM_NODES : the number of nodes in the node pool,
for example 3 .

Create an H100 node pool for the second cluster:

gcloud container node-pools create h100 \ --accelerator "type=nvidia-h100-80gb,count=2,gpu-driver-version=latest" \ --project = PROJECT_ID \ --location = CLUSTER_2_ZONE \ --node-locations = CLUSTER_2_ZONE \ --cluster = CLUSTER_2_NAME \ --machine-type = NODE_POOL_MACHINE_TYPE \ --num-nodes = NUM_NODES \ --spot \ --async # Allows the command to return immediately

Replace the following:

- PROJECT_ID : your project ID.

- CLUSTER_2_ZONE : the zone for the second cluster,
for example us-east4-a .

- CLUSTER_2_NAME : the name of the second cluster,
for example gke-east .

- NODE_POOL_MACHINE_TYPE : the machine type for the
node pool, for example a3-highgpu-2g .

- NUM_NODES : the number of nodes in the node pool,
for example 3 .

- For the second cluster, get credentials and create a secret for the Hugging Face token: gcloud container clusters get-credentials CLUSTER_2_NAME \ --location CLUSTER_2_ZONE \ --project = PROJECT_ID kubectl create secret generic hf-token --from-literal = token = HF_TOKEN Replace the following: CLUSTER_2_NAME : the name of the second cluster,
for example gke-east . CLUSTER_2_ZONE : the zone for the second cluster,
for example us-east4-a . PROJECT_ID : your project ID. HF_TOKEN : your Hugging Face access token.

For the second cluster, get credentials and create a secret for the Hugging Face token:

gcloud container clusters get-credentials CLUSTER_2_NAME \ --location CLUSTER_2_ZONE \ --project = PROJECT_ID kubectl create secret generic hf-token --from-literal = token = HF_TOKEN

Replace the following:

- CLUSTER_2_NAME : the name of the second cluster,
for example gke-east .

- CLUSTER_2_ZONE : the zone for the second cluster,
for example us-east4-a .

- PROJECT_ID : your project ID.

- HF_TOKEN : your Hugging Face access token.

### Register clusters to a fleet

To enable multi-cluster capabilities, such as the multi-cluster GKE
Inference Gateway, register your clusters to a
fleet.

- Set the API endpoint override to prevent mTLS issues during registration. gcloud config set api_endpoint_overrides/container https://container.googleapis.com/

Set the API endpoint override to prevent mTLS issues during registration.

gcloud config set api_endpoint_overrides/container https://container.googleapis.com/

- Register both clusters to your project's fleet: gcloud container fleet memberships register CLUSTER_1_NAME \ --gke-cluster CLUSTER_1_ZONE / CLUSTER_1_NAME \ --location = global \ --project = PROJECT_ID gcloud container fleet memberships register CLUSTER_2_NAME \ --gke-cluster CLUSTER_2_ZONE / CLUSTER_2_NAME \ --location = global \ --project = PROJECT_ID Replace the following: CLUSTER_1_NAME : the name of the first cluster,
for example gke-west . CLUSTER_1_ZONE : the zone for the first cluster,
for example europe-west3-c . PROJECT_ID : your project ID. CLUSTER_2_NAME : the name of the second cluster,
for example gke-east . CLUSTER_2_ZONE : the zone for the second cluster,
for example us-east4-a .

Register both clusters to your project's fleet:

gcloud container fleet memberships register CLUSTER_1_NAME \ --gke-cluster CLUSTER_1_ZONE / CLUSTER_1_NAME \ --location = global \ --project = PROJECT_ID gcloud container fleet memberships register CLUSTER_2_NAME \ --gke-cluster CLUSTER_2_ZONE / CLUSTER_2_NAME \ --location = global \ --project = PROJECT_ID

Replace the following:

- CLUSTER_1_NAME : the name of the first cluster,
for example gke-west .

- CLUSTER_1_ZONE : the zone for the first cluster,
for example europe-west3-c .

- PROJECT_ID : your project ID.

- CLUSTER_2_NAME : the name of the second cluster,
for example gke-east .

- CLUSTER_2_ZONE : the zone for the second cluster,
for example us-east4-a .

- To allow a single Gateway to manage traffic across multiple clusters, enable
the multi-cluster Ingress feature and designate a config cluster: gcloud container fleet ingress enable \ --config-membership = projects/ PROJECT_ID /locations/global/memberships/ CLUSTER_1_NAME Replace the following: PROJECT_ID : your project ID. CLUSTER_1_NAME : the name of the first cluster,
for example gke-west .

To allow a single Gateway to manage traffic across multiple clusters, enable
the multi-cluster Ingress feature and designate a config cluster:

gcloud container fleet ingress enable \ --config-membership = projects/ PROJECT_ID /locations/global/memberships/ CLUSTER_1_NAME

Replace the following:

- PROJECT_ID : your project ID.

- CLUSTER_1_NAME : the name of the first cluster,
for example gke-west .

### Create proxy-only subnets

For an internal gateway, create a proxy-only subnet in each region. The internal
Gateway's Envoy proxies use these dedicated subnets to handle traffic within
your VPC network.

Warning: Google Cloud allows only one proxy-only subnet per region in each VPC network. If the target region already contains a proxy-only subnet with purpose=REGIONAL_MANAGED_PROXY setting, creating the GLOBAL_MANAGED_PROXY subnet fails. You must delete the existing regional proxy-only subnet first. Deleting a regional proxy-only subnet affects any regional Envoy-based load balancers in that region that use it, so plan the change accordingly.

- Create a subnet in the first cluster's region: gcloud compute networks subnets create CLUSTER_1_REGION -subnet \ --purpose = GLOBAL_MANAGED_PROXY \ --role = ACTIVE \ --region = CLUSTER_1_REGION \ --network = default \ --range = 10 .0.0.0/23 \ --project = PROJECT_ID

Create a subnet in the first cluster's region:

gcloud compute networks subnets create CLUSTER_1_REGION -subnet \ --purpose = GLOBAL_MANAGED_PROXY \ --role = ACTIVE \ --region = CLUSTER_1_REGION \ --network = default \ --range = 10 .0.0.0/23 \ --project = PROJECT_ID

- Create a subnet in the second cluster's region: gcloud compute networks subnets create CLUSTER_2_REGION -subnet \ --purpose = GLOBAL_MANAGED_PROXY \ --role = ACTIVE \ --region = CLUSTER_2_REGION \ --network = default \ --range = 10 .5.0.0/23 \ --project = PROJECT_ID Replace the following: PROJECT_ID : your project ID. CLUSTER_1_REGION : the region for the first
cluster, for example europe-west3 . CLUSTER_2_REGION : the region for the second
cluster, for example us-east4 .

Create a subnet in the second cluster's region:

gcloud compute networks subnets create CLUSTER_2_REGION -subnet \ --purpose = GLOBAL_MANAGED_PROXY \ --role = ACTIVE \ --region = CLUSTER_2_REGION \ --network = default \ --range = 10 .5.0.0/23 \ --project = PROJECT_ID

Replace the following:

- PROJECT_ID : your project ID.

- CLUSTER_1_REGION : the region for the first
cluster, for example europe-west3 .

- CLUSTER_2_REGION : the region for the second
cluster, for example us-east4 .

### Install the required CustomResourceDefinitions

The multi-cluster GKE Inference Gateway uses
custom resources such as InferencePool and InferenceObjective. The
GKE Gateway API controller manages the InferencePool CustomResourceDefinition. However, you must manually install the InferenceObjective
CustomResourceDefinition, which is in alpha, on your clusters.

- Define context variables for your clusters: CLUSTER1_CONTEXT = "gke_ PROJECT_ID _ CLUSTER_1_ZONE _ CLUSTER_1_NAME " CLUSTER2_CONTEXT = "gke_ PROJECT_ID _ CLUSTER_2_ZONE _ CLUSTER_2_NAME " Replace the following: PROJECT_ID : your project ID. CLUSTER_1_ZONE : the zone for the first cluster, for example europe-west3-c . CLUSTER_1_NAME : the name of the first cluster, for example gke-west . CLUSTER_2_ZONE : the zone for the second cluster, for example us-east4-a . CLUSTER_2_NAME : the name of the second cluster, for example gke-east .

Define context variables for your clusters:

CLUSTER1_CONTEXT = "gke_ PROJECT_ID _ CLUSTER_1_ZONE _ CLUSTER_1_NAME " CLUSTER2_CONTEXT = "gke_ PROJECT_ID _ CLUSTER_2_ZONE _ CLUSTER_2_NAME "

Replace the following:

- PROJECT_ID : your project ID.

- CLUSTER_1_ZONE : the zone for the first cluster, for example europe-west3-c .

- CLUSTER_1_NAME : the name of the first cluster, for example gke-west .

- CLUSTER_2_ZONE : the zone for the second cluster, for example us-east4-a .

- CLUSTER_2_NAME : the name of the second cluster, for example gke-east .

- Install the InferenceObjective CustomResourceDefinition on both clusters: kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api-inference-extension/v1.5.0/config/crd/bases/inference.networking.x-k8s.io_inferenceobjectives.yaml --context = $CLUSTER1_CONTEXT kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api-inference-extension/v1.5.0/config/crd/bases/inference.networking.x-k8s.io_inferenceobjectives.yaml --context = $CLUSTER2_CONTEXT

Install the InferenceObjective CustomResourceDefinition on both clusters:

kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api-inference-extension/v1.5.0/config/crd/bases/inference.networking.x-k8s.io_inferenceobjectives.yaml --context = $CLUSTER1_CONTEXT kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api-inference-extension/v1.5.0/config/crd/bases/inference.networking.x-k8s.io_inferenceobjectives.yaml --context = $CLUSTER2_CONTEXT

### Deploy resources to the target clusters

To make your AI/ML inference workloads available on each cluster, deploy the
required resources, such as the model servers and InferenceObjective
custom resources.

Note: The examples in this document use vLLM, but the multi-cluster
Inference Gateway is model-server platform-independent and also
works with other model servers, such as SGLang. If you use a different model
server, adjust the following settings:

- Serving port. Set the InferencePool target port, the HealthCheckPolicy port, and the AutoscalingMetric endpoint port to your
model server's serving port. For example, SGLang serves on port 30000 by
default instead of port 8000 .

- Metric names. Metric names are specific to each model server. For
example, SGLang reports KV cache utilization as the sglang:token_usage metric instead of vllm:kv_cache_usage_perc metric. Map your model server's
metric to the kv-cache export name in the AutoscalingMetric resource.
Custom metric extraction for model servers other than vLLM requires a
compatible Endpoint Picker (EPP) image; use the most recent supported chart
release.

- Multi-node model serving. If one model replica spans multiple nodes (for
example, when you use the LeaderWorkerSet API to serve a large model),
only the leader Pod (rank 0) serves the API. Configure the InferencePool modelServers.matchLabels selector to match only leader Pods—for example,
by adding apps.kubernetes.io/pod-index: "0" label. If the selector also
matches worker Pods, the gateway routes requests to Pods that can't serve
them, and those requests fail with an HTTP 404 Not Found status code.

- Deploy the model servers to both clusters: kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api-inference-extension/v1.5.0/config/manifests/vllm/gpu-deployment.yaml --context = $CLUSTER1_CONTEXT kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api-inference-extension/v1.5.0/config/manifests/vllm/gpu-deployment.yaml --context = $CLUSTER2_CONTEXT

Deploy the model servers to both clusters:

kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api-inference-extension/v1.5.0/config/manifests/vllm/gpu-deployment.yaml --context = $CLUSTER1_CONTEXT kubectl apply -f https://raw.githubusercontent.com/kubernetes-sigs/gateway-api-inference-extension/v1.5.0/config/manifests/vllm/gpu-deployment.yaml --context = $CLUSTER2_CONTEXT

- Deploy the InferenceObjective resources to both clusters. Save the
following sample manifest to a file named inference-objective.yaml : apiVersion : inference.networking.x-k8s.io/v1alpha2 kind : InferenceObjective metadata : name : food-review spec : priority : 10 poolRef : name : vllm-qwen3-32b group : "inference.networking.k8s.io"

Deploy the InferenceObjective resources to both clusters. Save the
following sample manifest to a file named inference-objective.yaml :

apiVersion : inference.networking.x-k8s.io/v1alpha2 kind : InferenceObjective metadata : name : food-review spec : priority : 10 poolRef : name : vllm-qwen3-32b group : "inference.networking.k8s.io"

- Apply the manifest to both clusters: kubectl apply -f inference-objective.yaml --context = $CLUSTER1_CONTEXT kubectl apply -f inference-objective.yaml --context = $CLUSTER2_CONTEXT Replace the following: $CLUSTER1_CONTEXT: the context for the first cluster, for example gke_my-project_europe-west3-c_gke-west . $CLUSTER2_CONTEXT: the context for the second cluster, for example gke_my-project_us-east4-a_gke-east .

Apply the manifest to both clusters:

kubectl apply -f inference-objective.yaml --context = $CLUSTER1_CONTEXT kubectl apply -f inference-objective.yaml --context = $CLUSTER2_CONTEXT

Replace the following:

- $CLUSTER1_CONTEXT: the context for the first cluster, for example gke_my-project_europe-west3-c_gke-west .

- $CLUSTER2_CONTEXT: the context for the second cluster, for example gke_my-project_us-east4-a_gke-east .

- Deploy the InferencePool resources to both clusters by using Helm: helm install vllm-qwen3-32b \ --kube-context $CLUSTER1_CONTEXT \ --set inferencePool.modelServers.matchLabels.app = vllm-qwen3-32b \ --set provider.name = gke \ --set inferenceExtension.monitoring.gke.enabled = true \ --version v1.5.0 \ oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool helm install vllm-qwen3-32b \ --kube-context $CLUSTER2_CONTEXT \ --set inferencePool.modelServers.matchLabels.app = vllm-qwen3-32b \ --set provider.name = gke \ --set inferenceExtension.monitoring.gke.enabled = true \ --version v1.5.0 \ oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool The preceding commands use version v1.5.0 of the Helm chart because it is a
recommended version for this setup. The Helm chart also installs a GCPBackendPolicy custom resource and a HealthCheckPolicy custom resource
intended for single-cluster use. In version v1.1.0 of the InferencePool Helm chart, the --set
inferencePool.targetPortNumber flag might be ignored, and the target port
defaults to 8000 . If your model server listens on a different port (for
example, SGLang serves on port 30000 by default), verify the port after
installation: kubectl get inferencepool POOL_NAME -o jsonpath = '{.spec.targetPorts}' \ --context = CLUSTER_CONTEXT If the port is incorrect, patch the InferencePool custom resource before you export it: kubectl patch inferencepool POOL_NAME --type = merge \ -p '{"spec":{"targetPorts":[{"number":TARGET_PORT}]}}' \ --context = CLUSTER_CONTEXT

Deploy the InferencePool resources to both clusters by using Helm:

helm install vllm-qwen3-32b \ --kube-context $CLUSTER1_CONTEXT \ --set inferencePool.modelServers.matchLabels.app = vllm-qwen3-32b \ --set provider.name = gke \ --set inferenceExtension.monitoring.gke.enabled = true \ --version v1.5.0 \ oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool

helm install vllm-qwen3-32b \ --kube-context $CLUSTER2_CONTEXT \ --set inferencePool.modelServers.matchLabels.app = vllm-qwen3-32b \ --set provider.name = gke \ --set inferenceExtension.monitoring.gke.enabled = true \ --version v1.5.0 \ oci://registry.k8s.io/gateway-api-inference-extension/charts/inferencepool

The preceding commands use version v1.5.0 of the Helm chart because it is a
recommended version for this setup. The Helm chart also installs a GCPBackendPolicy custom resource and a HealthCheckPolicy custom resource
intended for single-cluster use.

In version v1.1.0 of the InferencePool Helm chart, the --set
inferencePool.targetPortNumber flag might be ignored, and the target port
defaults to 8000 . If your model server listens on a different port (for
example, SGLang serves on port 30000 by default), verify the port after
installation:

kubectl get inferencepool POOL_NAME -o jsonpath = '{.spec.targetPorts}' \ --context = CLUSTER_CONTEXT

If the port is incorrect, patch the InferencePool custom resource before you export it:

kubectl patch inferencepool POOL_NAME --type = merge \ -p '{"spec":{"targetPorts":[{"number":TARGET_PORT}]}}' \ --context = CLUSTER_CONTEXT

- Mark the InferencePool resources as exported on both clusters. This
annotation makes the InferencePool available for import by the config
cluster, which is a required step for multi-cluster routing. kubectl annotate inferencepool vllm-qwen3-32b networking.gke.io/export = "True" \ --context = $CLUSTER1_CONTEXT kubectl annotate inferencepool vllm-qwen3-32b networking.gke.io/export = "True" \ --context = $CLUSTER2_CONTEXT

Mark the InferencePool resources as exported on both clusters. This
annotation makes the InferencePool available for import by the config
cluster, which is a required step for multi-cluster routing.

kubectl annotate inferencepool vllm-qwen3-32b networking.gke.io/export = "True" \ --context = $CLUSTER1_CONTEXT

kubectl annotate inferencepool vllm-qwen3-32b networking.gke.io/export = "True" \ --context = $CLUSTER2_CONTEXT

### Deploy resources to the config cluster

To define how traffic is routed and load-balanced across the InferencePool
resources in all registered clusters, deploy the Gateway , HTTPRoute , and HealthCheckPolicy resources. You deploy these resources only to the designated config cluster, which is gke-west in this document.

- Create a file named mcig.yaml with the following content: --- apiVersion : gateway.networking.k8s.io/v1 kind : Gateway metadata : name : cross-region-gateway namespace : default spec : gatewayClassName : gke-l7-cross-regional-internal-managed-mc addresses : - type : networking.gke.io/ephemeral-ipv4-address/europe-west3 value : "europe-west3" - type : networking.gke.io/ephemeral-ipv4-address/us-east4 value : "us-east4" listeners : - name : http protocol : HTTP port : 80 --- apiVersion : gateway.networking.k8s.io/v1 kind : HTTPRoute metadata : name : vllm-qwen3-32b-default spec : parentRefs : - name : cross-region-gateway kind : Gateway rules : - backendRefs : - group : networking.gke.io kind : GCPInferencePoolImport name : vllm-qwen3-32b --- apiVersion : networking.gke.io/v1 kind : HealthCheckPolicy metadata : name : health-check-policy namespace : default spec : targetRef : group : "networking.gke.io" kind : GCPInferencePoolImport name : vllm-qwen3-32b default : config : type : HTTP httpHealthCheck : requestPath : /health port : 8000

Create a file named mcig.yaml with the following content:

--- apiVersion : gateway.networking.k8s.io/v1 kind : Gateway metadata : name : cross-region-gateway namespace : default spec : gatewayClassName : gke-l7-cross-regional-internal-managed-mc addresses : - type : networking.gke.io/ephemeral-ipv4-address/europe-west3 value : "europe-west3" - type : networking.gke.io/ephemeral-ipv4-address/us-east4 value : "us-east4" listeners : - name : http protocol : HTTP port : 80 --- apiVersion : gateway.networking.k8s.io/v1 kind : HTTPRoute metadata : name : vllm-qwen3-32b-default spec : parentRefs : - name : cross-region-gateway kind : Gateway rules : - backendRefs : - group : networking.gke.io kind : GCPInferencePoolImport name : vllm-qwen3-32b --- apiVersion : networking.gke.io/v1 kind : HealthCheckPolicy metadata : name : health-check-policy namespace : default spec : targetRef : group : "networking.gke.io" kind : GCPInferencePoolImport name : vllm-qwen3-32b default : config : type : HTTP httpHealthCheck : requestPath : /health port : 8000

- Apply the manifest: kubectl apply -f mcig.yaml --context = $CLUSTER1_CONTEXT

Apply the manifest:

kubectl apply -f mcig.yaml --context = $CLUSTER1_CONTEXT

### Enable custom metrics reporting

To enable custom metrics reporting and help improve cross-regional load balancing,
you export KV Cache usage metrics from all clusters. The load balancer uses this
exported KV Cache usage data as a custom load signal. Using this custom load
signal allows for more intelligent load balancing decisions based on each
cluster's actual workload.

- Create a file named metrics.yaml with the following content: apiVersion : autoscaling.gke.io/v1beta1 kind : AutoscalingMetric metadata : name : gpu-cache namespace : default spec : selector : matchLabels : app : vllm-qwen3-32b endpoints : - port : 8000 path : /metrics metrics : - name : vllm:kv_cache_usage_perc # For vLLM versions v0.10.2 and newer exportName : kv-cache - name : vllm:gpu_cache_usage_perc # For vLLM versions v0.6.2 and newer exportName : kv-cache-old

Create a file named metrics.yaml with the following content:

apiVersion : autoscaling.gke.io/v1beta1 kind : AutoscalingMetric metadata : name : gpu-cache namespace : default spec : selector : matchLabels : app : vllm-qwen3-32b endpoints : - port : 8000 path : /metrics metrics : - name : vllm:kv_cache_usage_perc # For vLLM versions v0.10.2 and newer exportName : kv-cache - name : vllm:gpu_cache_usage_perc # For vLLM versions v0.6.2 and newer exportName : kv-cache-old

- Apply the metrics configuration to both clusters: kubectl apply -f metrics.yaml --context = $CLUSTER1_CONTEXT kubectl apply -f metrics.yaml --context = $CLUSTER2_CONTEXT

Apply the metrics configuration to both clusters:

kubectl apply -f metrics.yaml --context = $CLUSTER1_CONTEXT kubectl apply -f metrics.yaml --context = $CLUSTER2_CONTEXT

### Configure the load balancing policy

To optimize how requests for AI/ML inference are distributed across your
GKE clusters, configure a load balancing policy. An appropriate
balancing mode helps to ensure efficient resource utilization, prevents
overloading individual clusters, and helps improve the performance and responsiveness
of your inference services.

#### Configure timeouts

If your requests are expected to have long durations, configure a longer timeout
for the load balancer. In the GCPBackendPolicy , set the timeoutSec field to
at least twice your estimated P99 request latency. For long-context inference
workloads at high concurrency, you might need a timeout of up to 3600 seconds.
For example, the following manifest sets the load balancer timeout to 600 seconds.

apiVersion : networking.gke.io/v1 kind : GCPBackendPolicy metadata : name : my-backend-policy spec : targetRef : group : "networking.gke.io" kind : GCPInferencePoolImport name : vllm-qwen3-32b default : timeoutSec : 600 balancingMode : CUSTOM_METRICS trafficDuration : LONG customMetrics : - name : gke.named_metrics.kv-cache dryRun : false maxUtilizationPercent : 60

For more information,
see multi-cluster Gateway limitations .

Because the Custom metrics and In-flight requests load balancing modes are
mutually exclusive, configure only one of these modes in your GCPBackendPolicy .

Choose a load balancing mode for your deployment.

### Custom metrics

For optimal load balancing, start with a target utilization of 60%. To
achieve this target, set maxUtilizationPercent: 60 in your GCPBackendPolicy 's customMetrics configuration.

- Create a file named backend-policy.yaml with the following content to
enable load balancing based on the kv-cache custom metric: apiVersion : networking.gke.io/v1 kind : GCPBackendPolicy metadata : name : my-backend-policy spec : targetRef : group : "networking.gke.io" kind : GCPInferencePoolImport name : vllm-qwen3-32b default : balancingMode : CUSTOM_METRICS trafficDuration : LONG customMetrics : - name : gke.named_metrics.kv-cache dryRun : false maxUtilizationPercent : 60

Create a file named backend-policy.yaml with the following content to
enable load balancing based on the kv-cache custom metric:

apiVersion : networking.gke.io/v1 kind : GCPBackendPolicy metadata : name : my-backend-policy spec : targetRef : group : "networking.gke.io" kind : GCPInferencePoolImport name : vllm-qwen3-32b default : balancingMode : CUSTOM_METRICS trafficDuration : LONG customMetrics : - name : gke.named_metrics.kv-cache dryRun : false maxUtilizationPercent : 60

- Apply the new policy: kubectl apply -f backend-policy.yaml --context = $CLUSTER1_CONTEXT

Apply the new policy:

kubectl apply -f backend-policy.yaml --context = $CLUSTER1_CONTEXT

### In-flight requests

To use the in-flight balancing mode, estimate the number of in-flight requests
each backend can handle and explicitly configure a capacity value.

- Create a file named backend-policy.yaml with the following content to
enable load balancing based on the number of in-flight requests: kind : GCPBackendPolicy apiVersion : networking.gke.io/v1 metadata : name : my-backend-policy spec : targetRef : group : "networking.gke.io" kind : GCPInferencePoolImport name : vllm-qwen3-32b default : balancingMode : IN_FLIGHT trafficDuration : LONG maxInFlightRequestsPerEndpoint : 1000 dryRun : false

Create a file named backend-policy.yaml with the following content to
enable load balancing based on the number of in-flight requests:

kind : GCPBackendPolicy apiVersion : networking.gke.io/v1 metadata : name : my-backend-policy spec : targetRef : group : "networking.gke.io" kind : GCPInferencePoolImport name : vllm-qwen3-32b default : balancingMode : IN_FLIGHT trafficDuration : LONG maxInFlightRequestsPerEndpoint : 1000 dryRun : false

- Apply the new policy: kubectl apply -f backend-policy.yaml --context = $CLUSTER1_CONTEXT

Apply the new policy:

kubectl apply -f backend-policy.yaml --context = $CLUSTER1_CONTEXT

## Verify the deployment

To verify the internal load balancer, you must send requests from within your
VPC network because, as internal load balancers use private IP
addresses. Run a temporary Pod inside one of the clusters to send requests from
your VPC network and verify the internal load balancer:

- From the new shell, get the Gateway IP address: GW_IP = $( kubectl get gateway/cross-region-gateway -n default --context = $CLUSTER1_CONTEXT -o jsonpath = '{.status.addresses[0].value}' )

From the new shell, get the Gateway IP address:

GW_IP = $( kubectl get gateway/cross-region-gateway -n default --context = $CLUSTER1_CONTEXT -o jsonpath = '{.status.addresses[0].value}' )

- Send a test request from a temporary Pod inside the cluster: kubectl run -it --rm --image = curlimages/curl curly --context = $CLUSTER1_CONTEXT -- \ curl -i -X POST ${ GW_IP } :80/v1/completions -H 'Content-Type: application/json' -d '{ "model": "Qwen/Qwen3-32B", "prompt": "What is the best pizza in the world?", "max_tokens": 100, "temperature": 0 }'

Send a test request from a temporary Pod inside the cluster:

kubectl run -it --rm --image = curlimages/curl curly --context = $CLUSTER1_CONTEXT -- \ curl -i -X POST ${ GW_IP } :80/v1/completions -H 'Content-Type: application/json' -d '{ "model": "Qwen/Qwen3-32B", "prompt": "What is the best pizza in the world?", "max_tokens": 100, "temperature": 0 }'

## What's next

- Learn more about the GKE Gateway API .

- Learn more about multi-cluster GKE Inference Gateway .

- Learn more about Multi Cluster Ingress .