# Syncing LDAP groups
Playbook for sync groups (RBAC) for OCP 4.x

As an administrator, you can use groups to manage users, change their permissions, and enhance collaboration. Your organization may have already created user groups and stored them in an LDAP server. OpenShift Container Platform can sync those LDAP records with internal OpenShift Container Platform records, enabling you to manage your groups in one place. OpenShift Container Platform currently supports group sync with LDAP servers using three common schemas for defining group membership: RFC 2307, Active Directory, and augmented Active Directory.

For more information on configuring LDAP, see Configuring an LDAP identity provider: 
https://docs.openshift.com/container-platform/4.9/authentication/identity_providers/configuring-ldap-identity-provider.html#configuring-ldap-identity-provider

```
NOTE:

You must have cluster-admin privileges to sync groups.
```
# About configuring LDAP sync

Before you can run LDAP sync, you need a sync configuration file. This file contains the following LDAP client configuration details:

- Configuration for connecting to your LDAP server.

- Sync configuration options that are dependent on the schema used in your LDAP server.

- An administrator-defined list of name mappings that maps OpenShift Container Platform group names to groups in your LDAP server.

The format of the configuration file depends upon the schema you are using: RFC 2307, Active Directory, or augmented Active Directory.

## LDAP client configuration

The LDAP client configuration section of the configuration defines the connections to your LDAP server.

### LDAP client configuration

~~~
url: ldap://10.0.0.0:389 
bindDN: cn=admin,dc=example,dc=com 
bindPassword: password 
insecure: false 
ca: my-ldap-ca-bundle.crt
~~~

1. The distinguished name (DN) of the branch of the directory where all searches will start from. It is required that you specify the top of your directory tree, but you can also specify a subtree in the directory.
2. The scope of the search. Valid values are base, one, or sub. If this is left undefined, then a scope of sub is assumed. Descriptions of the scope options can be found in the table below.
The behavior of the search with respect to aliases in the LDAP tree. 3. Valid values are never, search, base, or always. If this is left undefined, then the default is to always dereference aliases. Descriptions of the dereferencing behaviors can be found in the table below.
4. The time limit allowed for the search by the client, in seconds.  A value of 0 imposes no client-side limit.
5. A valid LDAP search filter. If this is left undefined, then the default is (objectClass=*).
6.The optional maximum size of response pages from the server, measured in LDAP entries. If set to 0, no size restrictions will be made on pages of responses. Setting paging sizes is necessary when queries return more entries than the client or server allow by default.

# About the RFC 2307 configuration file

The RFC 2307 schema requires you to provide an LDAP query definition for both user and group entries, as well as the attributes with which to represent them in the internal OpenShift Container Platform records.

For clarity, the group you create in OpenShift Container Platform should use attributes other than the distinguished name whenever possible for user- or administrator-facing fields. For example, identify the users of an OpenShift Container Platform group by their e-mail, and use the name of the group as the common name. The following configuration file creates these relationships:

### LDAP sync configuration that uses RFC 2307 schema: rfc2307_config.yaml

~~~
kind: LDAPSyncConfig
apiVersion: v1
url: ldap://LDAP_SERVICE_IP:389 
insecure: false 
rfc2307:
    groupsQuery:
        baseDN: "ou=groups,dc=example,dc=com"
        scope: sub
        derefAliases: never
        pageSize: 0
    groupUIDAttribute: dn 
    groupNameAttributes: [ cn ] 
    groupMembershipAttributes: [ member ] 
    usersQuery:
        baseDN: "ou=users,dc=example,dc=com"
        scope: sub
        derefAliases: never
        pageSize: 0
    userUIDAttribute: dn 
    userNameAttributes: [ mail ] 
    tolerateMemberNotFoundErrors: false
    tolerateMemberOutOfScopeErrors: false
~~~

1. The IP address and host of the LDAP server where this group’s record is stored.
2. When false, secure LDAP (ldaps://) URLs connect using TLS, and insecure LDAP (ldap://) URLs are upgraded to TLS. When true, no TLS connection is made to the server and you cannot use ldaps:// URL schemes.
3. The attribute that uniquely identifies a group on the LDAP server. You cannot specify groupsQuery filters when using DN for groupUIDAttribute. For fine-grained filtering, use the whitelist / blacklist method.
4. The attribute to use as the name of the group.
5. The attribute on the group that stores the membership information.
6. The attribute that uniquely identifies a user on the LDAP server. You cannot specify usersQuery filters when using DN for userUIDAttribute. For fine-grained filtering, use the whitelist / blacklist method.
7. The attribute to use as the name of the user in the OpenShift Container Platform group record.

## About the Active Directory configuration file

The Active Directory schema requires you to provide an LDAP query definition for user entries, as well as the attributes to represent them with in the internal OpenShift Container Platform group records.

For clarity, the group you create in OpenShift Container Platform should use attributes other than the distinguished name whenever possible for user- or administrator-facing fields. For example, identify the users of an OpenShift Container Platform group by their e-mail, but define the name of the group by the name of the group on the LDAP server. The following configuration file creates these relationships:

### LDAP sync configuration that uses Active Directory schema: active_directory_config.yaml

~~~
kind: LDAPSyncConfig
apiVersion: v1
url: ldap://LDAP_SERVICE_IP:389
activeDirectory:
    usersQuery:
        baseDN: "ou=users,dc=example,dc=com"
        scope: sub
        derefAliases: never
        filter: (objectclass=person)
        pageSize: 0
    userNameAttributes: [ mail ] 
    groupMembershipAttributes: [ memberOf ]
~~~

1. The attribute to use as the name of the user in the OpenShift Container Platform group record.
2. The attribute on the user that stores the membership information.

## About the augmented Active Directory configuration file

The augmented Active Directory schema requires you to provide an LDAP query definition for both user entries and group entries, as well as the attributes with which to represent them in the internal OpenShift Container Platform group records.

For clarity, the group you create in OpenShift Container Platform should use attributes other than the distinguished name whenever possible for user- or administrator-facing fields. For example, identify the users of an OpenShift Container Platform group by their e-mail, and use the name of the group as the common name. The following configuration file creates these relationships.

### LDAP sync configuration that uses augmented Active Directory schema: augmented_active_directory_config.yaml

~~~
kind: LDAPSyncConfig
apiVersion: v1
url: ldap://LDAP_SERVICE_IP:389
augmentedActiveDirectory:
    groupsQuery:
        baseDN: "ou=groups,dc=example,dc=com"
        scope: sub
        derefAliases: never
        pageSize: 0
    groupUIDAttribute: dn 
    groupNameAttributes: [ cn ] 
    usersQuery:
        baseDN: "ou=users,dc=example,dc=com"
        scope: sub
        derefAliases: never
        filter: (objectclass=person)
        pageSize: 0
    userNameAttributes: [ mail ] 
    groupMembershipAttributes: [ memberOf ]
~~~

1. The attribute that uniquely identifies a group on the LDAP server. You cannot specify groupsQuery filters when using DN for groupUIDAttribute. For fine-grained filtering, use the whitelist / blacklist method.
2. The attribute to use as the name of the group.
3. The attribute to use as the name of the user in the OpenShift Container Platform group record.
4. The attribute on the user that stores the membership information.

# Running LDAP sync

Once you have created a sync configuration file, you can begin to sync. OpenShift Container Platform allows administrators to perform a number of different sync types with the same server.

## Syncing the LDAP server with OpenShift Container Platform

You can sync all groups from the LDAP server with OpenShift Container Platform.

### Prerequisites

- Create a sync configuration file.

### Procedure

- To sync all groups from the LDAP server with OpenShift Container Platform:

~~~
$ oc adm groups sync --sync-config=config.yaml --confirm
~~~

## Syncing subgroups from the LDAP server with OpenShift Container Platform

You can sync a subset of LDAP groups with OpenShift Container Platform using whitelist files, blacklist files, or both.

### Prerequisites

- Create a sync configuration file.

### Procedure

- To sync a subset of LDAP groups with OpenShift Container Platform, use any the following commands:

~~~
$ oc adm groups sync --whitelist=<whitelist_file> \
                   --sync-config=config.yaml      \
                   --confirm
~~~

~~~
$ oc adm groups sync --blacklist=<blacklist_file> \
                   --sync-config=config.yaml      \
                   --confirm
~~~

~~~
$ oc adm groups sync <group_unique_identifier>    \
                   --sync-config=config.yaml      \
                   --confirm
~~~

~~~
$ oc adm groups sync <group_unique_identifier>  \
                   --whitelist=<whitelist_file> \
                   --blacklist=<blacklist_file> \
                   --sync-config=config.yaml    \
                   --confirm
~~~

~~~
$ oc adm groups sync --type=openshift           \
                   --whitelist=<whitelist_file> \
                   --sync-config=config.yaml    \
                   --confirm
~~~

## Running a group pruning job

An administrator can also choose to remove groups from OpenShift Container Platform records if the records on the LDAP server that created them are no longer present. The prune job will accept the same sync configuration file and whitelists or blacklists as used for the sync job.

For example:

~~~
$ oc adm prune groups --sync-config=/path/to/ldap-sync-config.yaml --confirm
~~~

~~~
$ oc adm prune groups --whitelist=/path/to/whitelist.txt --sync-config=/path/to/ldap-sync-config.yaml --confirm
~~~

~~~
$ oc adm prune groups --blacklist=/path/to/blacklist.txt --sync-config=/path/to/ldap-sync-config.yaml --confirm
~~~

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

5. Define a cluster role:

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

- 1. 	Reference to the service account created earlier in this procedure.
- 2. Reference to the cluster role created earlier in this procedure.

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
    url: ldaps://10.0.0.0:389                  
    insecure: false
    bindDN: cn=admin,dc=example,dc=com         
    bindPassword:
      file: "/etc/secrets/bindPassword"
    ca: /etc/ldap-ca/ca.crt
    rfc2307:                                   
      groupsQuery:
        baseDN: "ou=groups,dc=example,dc=com"  
        scope: sub
        filter: "(objectClass=groupOfMembers)"
        derefAliases: never
        pageSize: 0
      groupUIDAttribute: dn
      groupNameAttributes: [ cn ]
      groupMembershipAttributes: [ member ]
      usersQuery:
        baseDN: "ou=users,dc=example,dc=com"   
        scope: sub
        derefAliases: never
        pageSize: 0
      userUIDAttribute: dn
      userNameAttributes: [ uid ]
      tolerateMemberNotFoundErrors: false
      tolerateMemberOutOfScopeErrors: false
~~~

- 1. 	Define the sync configuration file.
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