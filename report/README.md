# OpenShift RBAC HTML Report — Ansible Playbook

## Purpose

This toolkit runs locally against an OpenShift cluster and produces a self-contained HTML report with:

- OpenShift identities, users and groups
- Roles and ClusterRoles
- RoleBindings and ClusterRoleBindings
- Verbs, API groups, resources, resource names and non-resource URLs
- ServiceAccounts and their bindings
- SCC characteristics, direct users/groups and RBAC `use` grants
- User-to-group-to-binding-to-role relationships
- Cluster scope versus namespace scope
- ClusterRole aggregation
- Risk candidates such as wildcards, `cluster-admin`, `bind`, `escalate`, `impersonate`, Secret access, pod exec, SCC use and RBAC mutation
- Inline charts and searchable tables
- Raw JSON evidence and collection error files

The playbook does not read Secret objects or Secret values.

## Requirements

### macOS

```bash
brew install ansible openshift-cli python@3
```

### RHEL 9

```bash
sudo dnf install -y ansible-core python3
```

Install a compatible `oc` binary from the OpenShift web console under **? → Command Line Tools**.

Validate:

```bash
ansible-playbook --version
oc version --client
python3 --version
```

No external Python modules or Ansible collections are required.

## Files

```text
ansible.cfg
inventory.ini
site.yml
files/generate_rbac_html.py
manifests/rbac-report-reader.yaml
README.md
```

## Authenticate

```bash
oc login https://api.<cluster-domain>:6443
oc whoami
oc whoami --show-server
oc get clusterversion
```

For a dedicated kubeconfig:

```bash
export KUBECONFIG="$HOME/.kube/openshift-production.yaml"
oc login https://api.<cluster-domain>:6443
```

## Validate permissions

```bash
oc auth can-i list identities.user.openshift.io
oc auth can-i list users.user.openshift.io
oc auth can-i list groups.user.openshift.io
oc auth can-i list roles.rbac.authorization.k8s.io --all-namespaces
oc auth can-i list rolebindings.rbac.authorization.k8s.io --all-namespaces
oc auth can-i list clusterroles.rbac.authorization.k8s.io
oc auth can-i list clusterrolebindings.rbac.authorization.k8s.io
oc auth can-i list serviceaccounts --all-namespaces
oc auth can-i list securitycontextconstraints.security.openshift.io
oc auth can-i get oauths.config.openshift.io/cluster
oc auth can-i get authentications.config.openshift.io/cluster
oc auth can-i get clusterversions.config.openshift.io/version
```

For a complete report, all commands should return `yes`.

### Optional read-only role

Edit the group in:

```text
manifests/rbac-report-reader.yaml
```

Apply:

```bash
oc apply -f manifests/rbac-report-reader.yaml
```

Or bind the role to the current user:

```bash
oc adm policy add-cluster-role-to-user \
  openshift-rbac-report-reader \
  "$(oc whoami)"
```

The role does not grant Secret access, RBAC modification, SCC use or impersonation.

## Run

Default kubeconfig:

```bash
ansible-playbook site.yml
```

Specific kubeconfig:

```bash
ansible-playbook site.yml \
  -e "kubeconfig_path=$HOME/.kube/openshift-production.yaml"
```

Custom output root:

```bash
ansible-playbook site.yml \
  -e "output_root=$HOME/openshift-rbac-reports"
```

## Output

```text
output/rbac-report-YYYYMMDDTHHMMSS/
├── openshift-rbac-report.html
└── evidence/
    ├── metadata.json
    ├── clusterversion.json
    ├── oauth.json
    ├── authentication.json
    ├── identities.json
    ├── users.json
    ├── groups.json
    ├── serviceaccounts.json
    ├── namespaces.json
    ├── roles.json
    ├── rolebindings.json
    ├── clusterroles.json
    ├── clusterrolebindings.json
    ├── sccs.json
    └── *.error
```

Open on macOS:

```bash
open output/rbac-report-*/openshift-rbac-report.html
```

Open on a Linux desktop:

```bash
xdg-open output/rbac-report-*/openshift-rbac-report.html
```

## Report logic

### RBAC scope

```text
ClusterRoleBinding → cluster-wide grant
RoleBinding        → namespace grant
```

A RoleBinding remains namespace-scoped even when it references a ClusterRole.

### Identity and user relationships

```text
Identity → OpenShift User → OpenShift Group → binding → role → rules
```

External LDAP/OIDC group membership can only be expanded when represented in OpenShift `Group` objects.

### SCC relationships

The report combines both SCC assignment mechanisms:

1. Direct `users` and `groups` fields in the SCC
2. RBAC rules granting verb `use` on `securitycontextconstraints`

## Validate effective authorization

User:

```bash
oc auth can-i --list \
  --as=user@example.com \
  -n <namespace>
```

User plus group:

```bash
oc auth can-i get secrets \
  --as=user@example.com \
  --as-group=<group> \
  -n <namespace>
```

ServiceAccount:

```bash
oc auth can-i --list \
  --as=system:serviceaccount:<namespace>:<service-account> \
  -n <namespace>
```

Who can:

```bash
oc adm policy who-can get secrets -n <namespace>
oc adm policy who-can create pods/exec -n <namespace>
```

SCC:

```bash
oc adm policy who-can use scc privileged
oc describe scc privileged
```

## Validate collection completeness

```bash
find output \
  -path '*/evidence/*.error' \
  -type f \
  -size +0c \
  -print \
  -exec cat {} \;
```

No output means all collection commands completed without an error.

## Security

The report contains sensitive authorization and identity metadata.

```bash
chmod -R go-rwx output/
```

Do not publish reports on an unauthenticated server or commit them to Git.

## References

- Red Hat OpenShift Container Platform 4.18 — Using RBAC  
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/authentication_and_authorization/using-rbac

- Red Hat OpenShift Container Platform 4.18 — RBAC APIs  
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html-single/rbac_apis/

- Red Hat OpenShift Container Platform 4.18 — Managing Security Context Constraints  
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/authentication_and_authorization/managing-pod-security-policies

- Ansible documentation  
  https://docs.ansible.com/ansible/latest/
