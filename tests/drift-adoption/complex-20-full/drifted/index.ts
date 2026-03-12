import * as pulumi from "@pulumi/pulumi";
import * as random from "@pulumi/random";
import * as command from "@pulumi/command";
import * as tls from "@pulumi/tls";

const apiCaKey = new tls.PrivateKey("api-ca-key", {
    algorithm: "RSA",
    rsaBits: 4096,
});

const apiCaCert = new tls.SelfSignedCert("api-ca-cert", {
    privateKeyPem: apiCaKey.privateKeyPem,
    subject: {
        organization: "Northwind Traders",
        commonName: "Api CA",
        country: "US",
    },
    validityPeriodHours: 8760,
    allowedUses: ["cert_signing", "crl_signing"],
    isCaCertificate: true,
});

const apiServerKey = new tls.PrivateKey("api-server-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const apiServerCsr = new tls.CertRequest("api-server-csr", {
    privateKeyPem: apiServerKey.privateKeyPem,
    subject: {
        commonName: "api.example.com",
        organization: "Northwind Traders",
    },
    dnsNames: ["api.example.com", "*.api.example.com"],
});

const apiServerCert = new tls.LocallySignedCert("api-server-cert", {
    certRequestPem: apiServerCsr.certRequestPem,
    caPrivateKeyPem: apiCaKey.privateKeyPem,
    caCertPem: apiCaCert.certPem,
    validityPeriodHours: 8760,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const apiStr = new random.RandomString("api-str", {
    length: 8,
    special: true,
    overrideSpecial: "~^&*",
});

const cachePass = new random.RandomPassword("cache-pass", {
    length: 32,
    special: true,
    minLower: 2,
});

const authInt = new random.RandomInteger("auth-int", {
    min: 1,
    max: 10000,
});

const gatewayId = new random.RandomId("gateway-id", {
    byteLength: 8,
    prefix: "svc-",
});

const apiPet = new random.RandomPet("api-pet", {
    length: 2,
    separator: "-",
    prefix: "dev",
});

const cacheShuffle = new random.RandomShuffle("cache-shuffle", {
    inputs: ["alpha", "beta", "gamma", "delta", "epsilon"],
});

const authUuid = new random.RandomUuid("auth-uuid", {
});

const gatewayStr1 = new random.RandomString("gateway-str-1", {
    length: 16,
    special: true,
    minUpper: 2,
    overrideSpecial: "._-",
});

const apiPass1 = new random.RandomPassword("api-pass-1", {
    length: 16,
    special: true,
    minLower: 6,
    minUpper: 3,
});

const cacheInt1 = new random.RandomInteger("cache-int-1", {
    min: 1024,
    max: 65535,
});

const apiCmd = new command.local.Command("api-cmd", {
    create: "echo \"api ready\"",
    environment: {
        APP_NAME: "api",
        LOG_LEVEL: "error",
        REGION: "eu-west-1",
    },
});

const cacheCmd = new command.local.Command("cache-cmd", {
    create: "echo \"Initializing cache\"",
    environment: {
        APP_NAME: "cache",
    },
    triggers: [cachePass.result],
});

const authCmd = new command.local.Command("auth-cmd", {
    create: "printf \"%s\\n\" \"auth\"",
    environment: {
        APP_NAME: "auth",
        PORT: "5000",
    },
});

const gatewayCmd = new command.local.Command("gateway-cmd", {
    create: "echo \"Initializing gateway\"",
    environment: {
        APP_NAME: "gateway",
        LOG_LEVEL: "warn",
    },
});

const apiCmd1 = new command.local.Command("api-cmd-1", {
    create: "echo \"HealthCheck: api\"",
    environment: {
        APP_NAME: "api",
        PORT: "3000",
        REGION: "eu-west-1",
    },
});

