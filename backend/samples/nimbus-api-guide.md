# Nimbus API — Developer Guide

## Introduction

The Nimbus API is a REST API for managing cloud storage buckets and objects.
The current stable version is v3. All requests are made to
`https://api.nimbus.example/v3` over HTTPS. Requests over plain HTTP are rejected.

## Authentication

Nimbus uses API keys passed in the `Authorization` header as a Bearer token:
`Authorization: Bearer <your_api_key>`. API keys are created in the dashboard and
can be scoped to read-only or read-write. Keys do not expire automatically but
can be revoked at any time. Never embed API keys in client-side code.

## Rate Limits

The default rate limit is 1,000 requests per minute per API key. Bulk endpoints
under `/v3/batch` are limited to 100 requests per minute. When a limit is
exceeded the API returns HTTP status 429 with a `Retry-After` header indicating
the number of seconds to wait. Rate limits reset on a rolling 60-second window.

## Pagination

List endpoints return at most 100 items per page. Use the `cursor` query
parameter with the value from `next_cursor` in the response to fetch the next
page. When `next_cursor` is null there are no more results.

## Uploading Objects

Objects up to 5 GB can be uploaded with a single PUT request. Files larger than
5 GB must use the multipart upload flow, which splits the file into parts of at
least 5 MB each. Each uploaded object supports up to 10 custom metadata keys.

## Error Handling

Errors return a JSON body with `code` and `message` fields. A 404 indicates the
bucket or object does not exist. A 403 indicates the API key lacks the required
scope. Server errors (5xx) should be retried with exponential backoff starting at
1 second, up to a maximum of 5 retries.

## Webhooks

Nimbus can send webhooks on object creation and deletion events. Webhook payloads
are signed with an HMAC-SHA256 signature in the `X-Nimbus-Signature` header.
Verify the signature using your webhook secret before trusting the payload.
