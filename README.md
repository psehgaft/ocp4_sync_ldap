# Syncing LDAP groups
Playbook for sync groups (RBAC) for OCP 4.x

As an administrator, you can use groups to manage users, change their permissions, and enhance collaboration. Your organization may have already created user groups and stored them in an LDAP server. OpenShift Container Platform can sync those LDAP records with internal OpenShift Container Platform records, enabling you to manage your groups in one place. OpenShift Container Platform currently supports group sync with LDAP servers using three common schemas for defining group membership: RFC 2307, Active Directory, and augmented Active Directory.

For more information on configuring LDAP, see Configuring an LDAP identity provider: 
https://docs.openshift.com/container-platform/4.9/authentication/identity_providers/configuring-ldap-identity-provider.html#configuring-ldap-identity-provider

```
NOTE:

You must have cluster-admin privileges to sync groups.
```
## Automatically syncing LDAP groups

You can automatically sync LDAP groups on a periodic basis by configuring a cron job.

### Prerequisites

- You have access to the cluster as a user with the cluster-admin role.

- You have configured an LDAP identity provider (IDP).

This procedure assumes that you created an LDAP secret named ldap-secret and a config map named ca-config-map.

### Procedure

1. Create a project where the cron job will run:

~~~
$ oc new-project ldap-sync
~~~

2. Locate the secret and config map that you created when configuring the LDAP identity provider and copy them to this new project.

The secret and config map exist in the openshift-config project and must be copied to the new ldap-sync project.

3. Define a service account: [ldap-sync-service-account.yaml]

~~~
kind: ServiceAccount
apiVersion: v1
metadata:
  name: ldap-group-syncer
  namespace: ldap-sync
~~~

4. Create the service account: [ldap-sync-cluster-role.yaml]

~~~
$ oc create -f ldap-sync-service-account.yaml
~~~

5. Define a cluster role: [ldap-sync-cluster-role.yaml]

~~~
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: ldap-group-syncer
rules:
  - apiGroups:
      - ''
      - user.openshift.io
    resources:
      - groups
    verbs:
      - get
      - list
      - create
      - update
~~~

6. Create the cluster role:

~~~
$ oc create -f ldap-sync-cluster-role.yaml
~~~

7. Define a cluster role binding to bind the cluster role to the service account: [ldap-sync-cluster-role-binding.yaml]

~~~
kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: ldap-group-syncer
subjects:
  - kind: ServiceAccount
    name: ldap-group-syncer              
    namespace: ldap-sync
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: ldap-group-syncer  
~~~

- 1. 	Reference to the service account created earlier in this procedure. [name: ldap-group-syncer ]
- 2. Reference to the cluster role created earlier in this procedure. [name: ldap-group-syncer]

8. Create the cluster role binding:

~~~
$ oc create -f ldap-sync-cluster-role-binding.yaml
~~~

9. Define a config map that specifies the sync configuration file: [ldap-sync-config-map.yaml]

~~~
kind: ConfigMap
apiVersion: v1
metadata:
  name: ldap-group-syncer
  namespace: ldap-sync
data:
  sync.yaml: |                                 
    kind: LDAPSyncConfig
    apiVersion: v1
    url: ldaps://example.com:3269                  
    insecure: false
    bindDN: "DC=users,DC=example,DC=com"         
    bindPassword:
      file: "/etc/secrets/bindPassword"
    ca: /etc/ldap-ca/ca.crt
    rfc2307:                                   
      groupsQuery:
        baseDN: "DC=users,DC=example,DC=com"  
        scope: sub
        filter: "(objectClass=groupOfMembers)"
        derefAliases: never
        pageSize: 0
      groupUIDAttribute: dn
      groupNameAttributes: [ cn ]
      groupMembershipAttributes: [ member ]
      usersQuery:
        baseDN: "DC=users,DC=example,DC=com"   
        scope: sub
        derefAliases: never
        pageSize: 0
      userUIDAttribute: dn
      userNameAttributes: [ uid ]
      tolerateMemberNotFoundErrors: false
      tolerateMemberOutOfScopeErrors: false
~~~

- 1. Define the sync configuration file.
- 2. Specify the URL.
- 3. Specify the bindDN.
- 4. This example uses the RFC2307 schema; adjust values as necessary. You can also use a different schema.
- 5. Specify the baseDN for groupsQuery.
- 6. Specify the baseDN for usersQuery.

10. Create the config map:

~~~
oc create -f ldap-sync-config-map.yaml
~~~

11. Define a cron job: [ldap-sync-cron-job.yaml]

~~~
kind: CronJob
apiVersion: batch/v1
metadata:
  name: ldap-group-syncer
  namespace: ldap-sync
spec:                                                                                
  schedule: "*/30 * * * *"                                                           
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      backoffLimit: 0
      template:
        spec:
          containers:
            - name: ldap-group-sync
              image: "registry.redhat.io/openshift4/ose-cli:latest"
              command:
                - "/bin/bash"
                - "-c"
                - "oc adm groups sync --sync-config=/etc/config/sync.yaml --confirm" 
              volumeMounts:
                - mountPath: "/etc/config"
                  name: "ldap-sync-volume"
                - mountPath: "/etc/secrets"
                  name: "ldap-bind-password"
                - mountPath: "/etc/ldap-ca"
                  name: "ldap-ca"
          volumes:
            - name: "ldap-sync-volume"
              configMap:
                name: "ldap-group-syncer"
            - name: "ldap-bind-password"
              secret:
                secretName: "ldap-secret"                                            
            - name: "ldap-ca"
              configMap:
                name: "ca-config-map"                                                
          restartPolicy: "Never"
          terminationGracePeriodSeconds: 30
          activeDeadlineSeconds: 500
          dnsPolicy: "ClusterFirst"
          serviceAccountName: "ldap-group-syncer"
~~~

- 1. Configure the settings for the cron job. See "Creating cron jobs" for more information on cron job settings.
- 2. The schedule for the job specified in cron format. This example cron job runs every 30 minutes. Adjust the frequency as necessary, making sure to take into account how long the sync takes to run.
- 3. The LDAP sync command for the cron job to run. Passes in the sync configuration file that was defined in the config map.
- 4. This secret was created when the LDAP IDP was configured.
- 5. This config map was created when the LDAP IDP was configured.

12. Create the cron job:

~~~
$ oc create -f ldap-sync-cron-job.yaml
~~~

## References

https://docs.openshift.com/container-platform/4.9/authentication/ldap-syncing.html