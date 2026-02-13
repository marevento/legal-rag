targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, prod)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string = 'swedencentral'

@description('Azure AI Search SKU: free, basic, or standard')
param searchServiceSku string = 'free'

@description('Azure OpenAI chat model deployment name')
param chatModelDeployment string = 'gpt-4o'

@description('Azure OpenAI mini model deployment name')
param chatMiniModelDeployment string = 'gpt-4o-mini'

@description('Azure OpenAI embedding model deployment name')
param embeddingModelDeployment string = 'text-embedding-3-large'

@description('Auth users JSON: {"username": "password", ...}')
@secure()
param authUsers string

var abbrs = loadJsonContent('abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

// Resource Group
resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: '${abbrs.resourceGroup}${environmentName}'
  location: location
  tags: tags
}

// Azure AI Search
module searchService 'core/search.bicep' = {
  name: 'search'
  scope: rg
  params: {
    name: '${abbrs.searchService}${resourceToken}'
    location: location
    sku: searchServiceSku
    tags: tags
  }
}

// Azure OpenAI
module openai 'core/openai.bicep' = {
  name: 'openai'
  scope: rg
  params: {
    name: '${abbrs.openAiAccount}${resourceToken}'
    location: location
    chatModelDeployment: chatModelDeployment
    chatMiniModelDeployment: chatMiniModelDeployment
    embeddingModelDeployment: embeddingModelDeployment
    tags: tags
  }
}

// Storage Account
module storage 'core/storage.bicep' = {
  name: 'storage'
  scope: rg
  params: {
    name: '${abbrs.storageAccount}${resourceToken}'
    location: location
    tags: tags
  }
}

// Container Registry
module registry 'core/registry.bicep' = {
  name: 'registry'
  scope: rg
  params: {
    name: '${abbrs.containerRegistry}${resourceToken}'
    location: location
    tags: tags
  }
}

// Key Vault
module keyVault 'core/keyvault.bicep' = {
  name: 'keyvault'
  scope: rg
  params: {
    name: '${abbrs.keyVault}${resourceToken}'
    location: location
    tags: tags
    authUsers: authUsers
  }
}

// Container Apps Environment + App
module containerApp 'core/container-app.bicep' = {
  name: 'container-app'
  scope: rg
  params: {
    name: '${abbrs.containerApp}${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'backend' })
    containerRegistryName: registry.outputs.name
    openaiEndpoint: openai.outputs.endpoint
    openaiKey: openai.outputs.key
    searchEndpoint: searchService.outputs.endpoint
    searchKey: searchService.outputs.key
    authUsers: authUsers
  }
}

// Outputs for azd
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_OPENAI_ENDPOINT string = openai.outputs.endpoint
output AZURE_SEARCH_ENDPOINT string = searchService.outputs.endpoint
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registry.outputs.loginServer
output AZURE_CONTAINER_APP_URL string = containerApp.outputs.url
