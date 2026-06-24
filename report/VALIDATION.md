# Validation

- `site.yml` parsed successfully as YAML.
- `manifests/rbac-report-reader.yaml` parsed successfully as multi-document YAML.
- `generate_rbac_html.py` passed `python3 -m py_compile`.
- The generator completed an end-to-end test using representative OpenShift RBAC, Identity, User, Group, ServiceAccount and SCC objects.
- The generated sample HTML is self-contained and contains inline CSS, JavaScript, charts and tables.

The Ansible playbook still requires execution against the target cluster to validate cluster-specific API permissions and data volume.
