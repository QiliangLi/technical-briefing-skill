--context = CLUSTER_CONTEXT If the port is incorrect, patch the InferencePool custom resource before you export it: kubectl patch inferencepool POOL_NAME --type = merge \ -p '{"spec":{"targetPorts":[{"number":TARGET_PORT}]}}' \ --context = CLUSTER_CONTEXT

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