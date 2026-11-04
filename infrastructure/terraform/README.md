# Terraform

No cloud environment is deployed. There is no Terraform workspace.

Azure infrastructure as code can live here when a workspace is ready to use it. OPS-1 does not add a module, a backend, a subscription id, a tenant id, or a credential. Do not add modules that require credentials until that workspace exists.

This directory has no configuration. Do not run `terraform apply` or `terraform plan` here.

Laboratory backup expectations and secret-management notes are in [../../docs/operations/](../../docs/operations/). Those notes and Compose are not an Azure deployment.
