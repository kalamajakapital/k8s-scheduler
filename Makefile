.PHONY: manifests

version_file := VERSION
VERSION := $(shell cat ${version_file})

manifests:
	kubectl apply -f manifests/rbac.yml
	kubectl apply -f manifests/configmap.yml
	kubectl apply -f manifests/deployment.yml
docker:
	docker build . -t kalamajakapital/workload-scheduler:${VERSION}
	docker push kalamajakapital/workload-scheduler:${VERSION}
