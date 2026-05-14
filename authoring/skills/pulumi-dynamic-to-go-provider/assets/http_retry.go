package main

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"time"
)

// doWithRetry mirrors stage 1's fetchWithRetry: retry on HTTP 5xx, 429, and
// network errors, with exponential backoff + jitter, capped at maxAttempts.
//
// Per E4b, this helper is used only for idempotent methods (GET, PATCH, DELETE).
// Create's POST goes through client.Do directly to avoid duplicate-create.
//
// On the final attempt the response is returned even if the status is in the
// retry range, so the caller can inspect the body for a meaningful error
// message. Caller is responsible for closing res.Body.
func doWithRetry(
	ctx context.Context,
	client *http.Client,
	method, url string,
	body []byte,
	maxAttempts int,
) (*http.Response, error) {
	var lastErr error
	for attempt := 0; attempt < maxAttempts; attempt++ {
		var bodyReader io.Reader
		if body != nil {
			bodyReader = bytes.NewReader(body)
		}
		req, err := http.NewRequestWithContext(ctx, method, url, bodyReader)
		if err != nil {
			return nil, fmt.Errorf("build %s %s: %w", method, url, err)
		}
		if body != nil {
			req.Header.Set("Content-Type", "application/json")
		}

		res, err := client.Do(req)
		if err != nil {
			lastErr = err
			if attempt < maxAttempts-1 {
				if waitErr := waitBackoff(ctx, attempt); waitErr != nil {
					return nil, waitErr
				}
				continue
			}
			return nil, fmt.Errorf("%s %s: %w", method, url, err)
		}

		isRetryable := res.StatusCode == http.StatusTooManyRequests ||
			(res.StatusCode >= 500 && res.StatusCode < 600)
		if isRetryable && attempt < maxAttempts-1 {
			lastErr = fmt.Errorf("HTTP %d %s", res.StatusCode, res.Status)
			res.Body.Close()
			if waitErr := waitBackoff(ctx, attempt); waitErr != nil {
				return nil, waitErr
			}
			continue
		}
		return res, nil
	}
	if lastErr == nil {
		lastErr = fmt.Errorf("doWithRetry exhausted %d attempts", maxAttempts)
	}
	return nil, lastErr
}

// waitBackoff sleeps for an exponentially-increasing duration with jitter,
// honouring ctx cancellation so a destroy mid-flight wakes up early.
func waitBackoff(ctx context.Context, attempt int) error {
	base := 200 * time.Millisecond * time.Duration(1<<attempt)
	jitter := time.Duration(rand.Int63n(int64(base) / 3)) //nolint:gosec // jitter
	d := base + jitter
	select {
	case <-time.After(d):
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

// errorFromResponse mirrors stage 1's errorFromResponse: format an error with
// method, URL, status, and as much of the response body as is available.
//
// Reads (and closes) res.Body; do not use res after calling this.
func errorFromResponse(method, url string, res *http.Response) error {
	defer res.Body.Close()
	body, readErr := io.ReadAll(res.Body)
	bodyStr := string(body)
	if readErr != nil {
		bodyStr = "<failed to read body: " + readErr.Error() + ">"
	}
	if bodyStr == "" {
		bodyStr = "<no body>"
	}
	return fmt.Errorf(
		"%s %s failed: %d %s\nResponse body: %s",
		method, url, res.StatusCode, res.Status, bodyStr,
	)
}
