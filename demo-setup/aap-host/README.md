# AAP host for the demo VM

Register the RHEL 9 instance `ao-ticket-demo-vm` in **Ansible Product Demos Inventory** so job templates can reach it.

The host is created with:

| Setting | Value |
| --- | --- |
| Name | `ao-ticket-demo-vm` |
| `ansible_host` | current public IP of that instance |
| `ansible_user` | `ec2-user` |
| Groups | `aws_rhel`, `aws_linux`, `os_linux` |

`create-host.sh` looks up the running instance, then creates the host or updates `ansible_host` if the host is already there. Group membership is added again; an existing association is left as it is.

## Run

From this directory, with a Controller token that can edit the inventory:

```bash
export CONTROLLER_HOST=https://aap-aap.apps.cluster-mshx8.dyn.redhatworkshops.io
export CONTROLLER_TOKEN=<controller-oauth-token>
export AWS_PROFILE=redhat-demo
export AWS_REGION=us-east-1

./create-host.sh
```

`CONTROLLER_HOST` is the Automation Controller API, not the MCP route. The AWS CLI must be able to describe `ao-ticket-demo-vm` in `us-east-1`. If the platform certificate is not trusted, set `CONTROLLER_INSECURE=1`.

Jobs still need a machine credential whose username is `ec2-user` and whose SSH private key is `ao-ticket-demo-key`. The **APD Machine Credential** logs in as `admin` and will not connect to this host.
