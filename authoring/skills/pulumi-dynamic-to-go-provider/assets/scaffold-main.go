// Scaffold for the provider's main.go.
//
// Substitute the placeholders marked with TODO comments. The shape is
// stable across most ports — Config + Configure + provider builder.

package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"time"

	p "github.com/pulumi/pulumi-go-provider"
	"github.com/pulumi/pulumi-go-provider/infer"
	"github.com/pulumi/pulumi/sdk/v3/go/common/tokens"
)

// TODO: Bump on any schema-affecting change.
const Version = "0.1.0"

// TODO: Set this to your provider's plugin name. The binary the engine
// looks for is `pulumi-resource-<Name>`. Example: "todo", "myapi".
const Name = "<PROVIDER_NAME>"

// Config holds provider-level configuration.
//
// Field naming convention:
//   - Exported fields with `pulumi:"name"` tags are user-supplied
//     configuration values that show up in the schema.
//   - Unexported fields (lowercase) are internal runtime state populated
//     by Configure; they are skipped by introspection and stay out of
//     the schema.
//
// TODO: Add user-supplied config fields here (URLs, API keys, etc.).
//   Example:
//     ServerUrl string `pulumi:"serverUrl"`
//     ApiKey    string `pulumi:"apiKey" provider:"secret"`  // marks as secret
type Config struct {
	// TODO: Replace with your config fields.
	ServerUrl string `pulumi:"serverUrl"`

	// Internal runtime state — populated by Configure, not part of schema.
	client *http.Client
}

// Annotate adds descriptions to config fields. They appear in the schema
// and propagate to generated SDK docs.
func (c *Config) Annotate(a infer.Annotator) {
	// TODO: Describe each config field.
	a.Describe(&c.ServerUrl, "Base URL of the upstream API.")
}

// Configure runs once at provider startup, after user config is unmarshalled
// but before any CRUD method is called. Initialise long-lived state here
// (HTTP clients, loggers, validated derived values, etc.).
//
// State set on c here is shared across all goroutines; it must be
// goroutine-safe. *http.Client is fine. A non-thread-safe cache wouldn't be.
func (c *Config) Configure(_ context.Context) error {
	c.client = &http.Client{Timeout: 30 * time.Second}
	// TODO: Validate config (e.g., parse URL, check required fields).
	return nil
}

func main() {
	provider, err := buildProvider()
	if err != nil {
		fmt.Fprintf(os.Stderr, "build provider: %s\n", err)
		os.Exit(1)
	}
	if err := provider.Run(context.Background(), Name, Version); err != nil {
		fmt.Fprintf(os.Stderr, "run provider: %s\n", err)
		os.Exit(1)
	}
}

func buildProvider() (p.Provider, error) {
	return infer.NewProviderBuilder().
		// TODO: Set the namespace. Affects schema's "namespace" field.
		WithNamespace("<NAMESPACE>").
		// TODO: One-line description of what the provider does.
		WithDescription("<PROVIDER_DESCRIPTION>").
		WithConfig(infer.Config(&Config{})).
		WithResources(
			// TODO: Register each resource type. Replace `&Xxx{}` with
			//       your resource's value. Add more lines for additional
			//       resources.
			infer.Resource(&Xxx{}),
		).
		WithModuleMap(map[tokens.ModuleName]tokens.ModuleName{
			// Maps the Go package name to the SDK module name (`index` is
			// the conventional default for single-package providers).
			"main": "index",
		}).
		Build()
}
