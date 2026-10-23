"""Checks that the getPetsWithTags Java service returns the petstore pets for a
tag, each with its id, name, status and associated tag names.

The deployed app is called over HTTP. The same data is fetched straight from the
petstore API and compared with what the service returned."""

import json
import os
import uuid

import pytest
from playwright.sync_api import sync_playwright

TIMEOUT_MS = int(os.environ.get("HOLODECK_TIMEOUT_MS", "60000"))
ARTIFACT_DIR = os.environ.get("HOLODECK_ARTIFACT_DIR")
PETSTORE_BASE_URL = os.environ.get("PETSTORE_BASE_URL", "https://petstore.swagger.io/v2")

SERVICE = "getPetsWithTags"
METHOD = "getPetsWithTags"
CANDIDATE_TAGS = ["tag1", "string", "dog", "cat"]


def _app_base(target_url):
    marker = "/react-preview/"
    assert marker in target_url, f"unexpected preview URL, no {marker} in it: {target_url}"
    return target_url.split(marker)[0]


def _save(name, payload):
    if ARTIFACT_DIR:
        with open(os.path.join(ARTIFACT_DIR, name), "w") as handle:
            json.dump(payload, handle, indent=2, default=str)


class Api:
    def __init__(self, playwright):
        target = os.environ["HOLODECK_TARGET_URL"]
        self.service_url = f"{_app_base(target)}/services/{SERVICE}/{METHOD}"
        headers = {}
        cookie = os.environ.get("HOLODECK_AUTH_COOKIE")
        if cookie:
            headers["Cookie"] = f"auth_cookie={cookie}"
        self.app = playwright.request.new_context(extra_http_headers=headers, timeout=TIMEOUT_MS)
        self.petstore_context = playwright.request.new_context(timeout=TIMEOUT_MS)

    def call_service(self, tag):
        """Calls the Java service. A method that is not served on GET is tried on POST."""
        response = self.app.get(self.service_url, params={"tag": tag})
        if response.status in (404, 405):
            response = self.app.post(self.service_url, params={"tag": tag})
        return response

    def service_json(self, tag):
        response = self.call_service(tag)
        assert response.ok, f"{self.service_url} returned {response.status}: {response.text()[:300]}"
        return response.json()

    def petstore(self, tag):
        response = self.petstore_context.get(f"{PETSTORE_BASE_URL}/pet/findByTags", params={"tags": tag})
        assert response.ok, f"petstore findByTags returned {response.status}"
        return response.json()


@pytest.fixture(scope="module")
def api():
    with sync_playwright() as playwright:
        yield Api(playwright)


@pytest.fixture(scope="module")
def known_tag(api):
    """A tag that the petstore has pets for, so the service has something to return."""
    for tag in CANDIDATE_TAGS:
        if api.petstore(tag):
            return tag
    pytest.fail(f"none of the tags {CANDIDATE_TAGS} has pets in the petstore, so the service cannot be checked")


def _tag_names(pet):
    return sorted(tag["name"] for tag in pet.get("tags") or [] if tag.get("name"))


def test_service_returns_a_list_of_pets(api, known_tag):
    result = api.service_json(known_tag)
    _save("service_response.json", result)
    assert isinstance(result, list), f"expected a list, got {type(result).__name__}"
    assert result, f"the service returned no pets for tag '{known_tag}'"


def test_each_pet_has_id_name_status_and_tags(api, known_tag):
    result = api.service_json(known_tag)
    assert result, f"the service returned no pets for tag '{known_tag}'"
    for pet in result:
        missing = [field for field in ("id", "name", "status", "tags") if field not in pet]
        assert not missing, f"pet {pet} is missing {missing}"
        assert isinstance(pet["tags"], list), f"tags of pet {pet['id']} is not a list"
        assert all(isinstance(tag, str) for tag in pet["tags"]), f"tags of pet {pet['id']} are not tag names"


def test_pets_and_tags_match_the_petstore_data(api, known_tag):
    expected = {pet["id"]: pet for pet in api.petstore(known_tag)}
    actual = {pet["id"]: pet for pet in api.service_json(known_tag)}
    _save("comparison.json", {"tag": known_tag, "expected_ids": sorted(expected), "actual_ids": sorted(actual)})
    assert set(actual) == set(expected), (
        f"pet ids differ for tag '{known_tag}': only in petstore {sorted(set(expected) - set(actual))}, "
        f"only in service {sorted(set(actual) - set(expected))}"
    )
    for pet_id, pet in actual.items():
        source = expected[pet_id]
        assert pet["name"] == source.get("name"), f"pet {pet_id}: name {pet['name']!r} != {source.get('name')!r}"
        assert pet["status"] == source.get("status"), f"pet {pet_id}: status {pet['status']!r} != {source.get('status')!r}"
        assert sorted(pet["tags"]) == _tag_names(source), f"pet {pet_id}: tags {pet['tags']} != {_tag_names(source)}"


def test_unknown_tag_returns_an_empty_list(api):
    result = api.service_json(f"no-such-tag-{uuid.uuid4().hex}")
    assert result == [], f"expected an empty list for an unknown tag, got {result}"
