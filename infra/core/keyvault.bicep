param name string
param location string
param tags object = {}

@secure()
param authUsers string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

resource authUsersSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'auth-users'
  properties: {
    value: authUsers
  }
}

output name string = keyVault.name
output uri string = keyVault.properties.vaultUri
