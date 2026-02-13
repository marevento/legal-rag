@description('Name of the Azure AI Search service')
param name string

@description('Location')
param location string

@description('SKU: free, basic, or standard')
param sku string = 'free'

param tags object = {}

resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
  }
}

output name string = searchService.name
output endpoint string = 'https://${searchService.name}.search.windows.net'
output key string = searchService.listAdminKeys().primaryKey
