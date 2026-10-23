Create a new Java service named `getPetsWithTags` that orchestrates the pet and tag data of the imported `petstore` API:

1. The service has one method, `getPetsWithTags`, with one input parameter, `tag` (String).
2. Invoke the imported `petstore` `findPetsByTags` API with that tag.
3. For every pet returned, build a result object with the fields `id`, `name`, `status` and `tags`, where `tags` is the list of the pet's associated tag names (Strings).
4. Return the list of these result objects.
5. If the API call fails or returns no pets, return an empty list.

Compile the project so the service is available. Do not change any page.
