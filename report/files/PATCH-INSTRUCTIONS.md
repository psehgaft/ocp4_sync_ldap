# Fix: `rules: null` in OpenShift RBAC HTML generator

## Cause

The previous generator used:

```python
x.get("rules", [])
```

The default `[]` is used only when the key is absent. When the API response contains:

```json
"rules": null
```

Python receives `None`, and iterating over it raises:

```text
TypeError: 'NoneType' object is not iterable
```

## Replacement

Copy the corrected generator over the existing file:

```bash
cp generate_rbac_html.py \
  /root/ocp4_sync_ldap-main/report/files/generate_rbac_html.py

chmod 0755 \
  /root/ocp4_sync_ldap-main/report/files/generate_rbac_html.py
```

Validate:

```bash
python3 -m py_compile \
  /root/ocp4_sync_ldap-main/report/files/generate_rbac_html.py
```

Run the playbook again:

```bash
cd /root/ocp4_sync_ldap-main/report

ansible-playbook site.yml
```

The corrected generator normalizes nullable fields in:

- `Role.rules`
- `ClusterRole.rules`
- `RoleBinding.subjects`
- `ClusterRoleBinding.subjects`
- `Group.users`
- OAuth identity-provider arrays
- SCC users, groups, strategies, volumes, and capabilities
- Object metadata and role references

A Role or ClusterRole with `rules: null` is included in the report and recorded under **Warnings** as a normalization event.
