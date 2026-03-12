import * as pulumi from "@pulumi/pulumi";
import * as random from "@pulumi/random";
import * as command from "@pulumi/command";
import * as tls from "@pulumi/tls";

const authCaKey = new tls.PrivateKey("auth-ca-key", {
    algorithm: "RSA",
    rsaBits: 4096,
});

const authCaCert = new tls.SelfSignedCert("auth-ca-cert", {
    privateKeyPem: authCaKey.privateKeyPem,
    subject: {
        organization: "Acme Corp",
        commonName: "Auth CA",
        country: "US",
    },
    validityPeriodHours: 43800,
    allowedUses: ["cert_signing", "crl_signing"],
    isCaCertificate: true,
});

const authServerKey = new tls.PrivateKey("auth-server-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const authServerCsr = new tls.CertRequest("auth-server-csr", {
    privateKeyPem: authServerKey.privateKeyPem,
    subject: {
        commonName: "auth.example.com",
        organization: "Acme Corp",
    },
    dnsNames: ["auth.example.com", "*.auth.example.com"],
});

const authServerCert = new tls.LocallySignedCert("auth-server-cert", {
    certRequestPem: authServerCsr.certRequestPem,
    caPrivateKeyPem: authCaKey.privateKeyPem,
    caCertPem: authCaCert.certPem,
    validityPeriodHours: 43800,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const workerCaKey = new tls.PrivateKey("worker-ca-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const workerCaCert = new tls.SelfSignedCert("worker-ca-cert", {
    privateKeyPem: workerCaKey.privateKeyPem,
    subject: {
        organization: "Northwind Traders",
        commonName: "Worker CA",
        country: "US",
    },
    validityPeriodHours: 17520,
    allowedUses: ["cert_signing", "crl_signing"],
    isCaCertificate: true,
});

const workerServerKey = new tls.PrivateKey("worker-server-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const workerServerCsr = new tls.CertRequest("worker-server-csr", {
    privateKeyPem: workerServerKey.privateKeyPem,
    subject: {
        commonName: "worker.example.com",
        organization: "Northwind Traders",
    },
    dnsNames: ["worker.example.com", "*.worker.example.com"],
});

const workerServerCert = new tls.LocallySignedCert("worker-server-cert", {
    certRequestPem: workerServerCsr.certRequestPem,
    caPrivateKeyPem: workerCaKey.privateKeyPem,
    caCertPem: workerCaCert.certPem,
    validityPeriodHours: 17520,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const webCaKey = new tls.PrivateKey("web-ca-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const webCaCert = new tls.SelfSignedCert("web-ca-cert", {
    privateKeyPem: webCaKey.privateKeyPem,
    subject: {
        organization: "Northwind Traders",
        commonName: "Web CA",
        country: "GB",
    },
    validityPeriodHours: 17520,
    allowedUses: ["cert_signing", "crl_signing"],
    isCaCertificate: true,
});

const webServerKey = new tls.PrivateKey("web-server-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const webServerCsr = new tls.CertRequest("web-server-csr", {
    privateKeyPem: webServerKey.privateKeyPem,
    subject: {
        commonName: "web.example.com",
        organization: "Northwind Traders",
    },
    dnsNames: ["web.example.com", "*.web.example.com"],
});

const webServerCert = new tls.LocallySignedCert("web-server-cert", {
    certRequestPem: webServerCsr.certRequestPem,
    caPrivateKeyPem: webCaKey.privateKeyPem,
    caCertPem: webCaCert.certPem,
    validityPeriodHours: 17520,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const gatewayCaKey = new tls.PrivateKey("gateway-ca-key", {
    algorithm: "RSA",
    rsaBits: 4096,
});

const gatewayCaCert = new tls.SelfSignedCert("gateway-ca-cert", {
    privateKeyPem: gatewayCaKey.privateKeyPem,
    subject: {
        organization: "Contoso Ltd",
        commonName: "Gateway CA",
        country: "US",
    },
    validityPeriodHours: 17520,
    allowedUses: ["cert_signing", "crl_signing"],
    isCaCertificate: true,
});

const gatewayServerKey = new tls.PrivateKey("gateway-server-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const gatewayServerCsr = new tls.CertRequest("gateway-server-csr", {
    privateKeyPem: gatewayServerKey.privateKeyPem,
    subject: {
        commonName: "gateway.example.com",
        organization: "Contoso Ltd",
    },
    dnsNames: ["gateway.example.com", "*.gateway.example.com"],
});

const gatewayServerCert = new tls.LocallySignedCert("gateway-server-cert", {
    certRequestPem: gatewayServerCsr.certRequestPem,
    caPrivateKeyPem: gatewayCaKey.privateKeyPem,
    caCertPem: gatewayCaCert.certPem,
    validityPeriodHours: 17520,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const authStr = new random.RandomString("auth-str", {
    length: 64,
    special: true,
    minUpper: 2,
    minNumeric: 2,
});

const workerPass = new random.RandomPassword("worker-pass", {
    length: 16,
    special: true,
    minUpper: 4,
});

const webInt = new random.RandomInteger("web-int", {
    min: 1,
    max: 1000,
});

const gatewayId = new random.RandomId("gateway-id", {
    byteLength: 16,
});

const apiPet = new random.RandomPet("api-pet", {
    length: 2,
});

const monitorShuffle = new random.RandomShuffle("monitor-shuffle", {
    inputs: ["alpha", "beta", "gamma", "delta", "epsilon"],
});

const authUuid = new random.RandomUuid("auth-uuid", {
});

const workerStr1 = new random.RandomString("worker-str-1", {
    length: 24,
    special: false,
    minLower: 1,
    minUpper: 1,
    minNumeric: 4,
    keepers: { ref: gatewayId.hex },
});

const webPass1 = new random.RandomPassword("web-pass-1", {
    length: 32,
    special: true,
    minUpper: 5,
});

const gatewayInt1 = new random.RandomInteger("gateway-int-1", {
    min: 1,
    max: 1000,
});

const apiId1 = new random.RandomId("api-id-1", {
    byteLength: 8,
});

const monitorPet1 = new random.RandomPet("monitor-pet-1", {
    length: 3,
});

const authShuffle1 = new random.RandomShuffle("auth-shuffle-1", {
    inputs: ["redis", "memcached", "dynamodb"],
    resultCount: 2,
});

const workerUuid1 = new random.RandomUuid("worker-uuid-1", {
});

const webStr2 = new random.RandomString("web-str-2", {
    length: 64,
    special: true,
    minLower: 2,
    minNumeric: 4,
    overrideSpecial: "!@#$%^&*",
});

const gatewayPass2 = new random.RandomPassword("gateway-pass-2", {
    length: 16,
    special: true,
    minUpper: 2,
});

const apiInt2 = new random.RandomInteger("api-int-2", {
    min: 1,
    max: 1000,
});

const monitorId2 = new random.RandomId("monitor-id-2", {
    byteLength: 4,
    prefix: "env-",
});

const authPet2 = new random.RandomPet("auth-pet-2", {
    length: 3,
    separator: ".",
});

const workerShuffle2 = new random.RandomShuffle("worker-shuffle-2", {
    inputs: ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
    resultCount: 2,
});

const webUuid2 = new random.RandomUuid("web-uuid-2", {
});

const gatewayStr3 = new random.RandomString("gateway-str-3", {
    length: 8,
    special: false,
    keepers: { ref: gatewayId.hex },
});

const apiPass3 = new random.RandomPassword("api-pass-3", {
    length: 24,
    special: true,
    minLower: 3,
    keepers: { ref: apiPet.id },
});

const monitorInt3 = new random.RandomInteger("monitor-int-3", {
    min: 1,
    max: 1000,
});

const authId3 = new random.RandomId("auth-id-3", {
    byteLength: 16,
    prefix: "app-",
});

const authCmd = new command.local.Command("auth-cmd", {
    create: "echo \"auth ready\"",
    environment: {
        APP_NAME: "auth",
        PORT: "9090",
    },
});

const workerCmd = new command.local.Command("worker-cmd", {
    create: "echo \"worker ready\"",
    environment: {
        APP_NAME: "worker",
        PORT: "9090",
        LOG_LEVEL: "info",
    },
});

const webCmd = new command.local.Command("web-cmd", {
    create: "echo \"HealthCheck: web\"",
    environment: {
        APP_NAME: "web",
        PORT: "9090",
        REGION: "us-east-1",
    },
});

const gatewayCmd = new command.local.Command("gateway-cmd", {
    create: "date +%s",
    environment: {
        APP_NAME: "gateway",
    },
});

const apiCmd = new command.local.Command("api-cmd", {
    create: "printf \"%s\\n\" \"api\"",
    environment: {
        APP_NAME: "api",
    },
});

const monitorCmd = new command.local.Command("monitor-cmd", {
    create: "echo \"monitor ready\"",
    environment: {
        APP_NAME: "monitor",
        REGION: "us-east-1",
    },
});

const authCmd1 = new command.local.Command("auth-cmd-1", {
    create: "printf \"%s\\n\" \"auth\"",
    environment: {
        APP_NAME: "auth",
        REGION: "us-east-1",
    },
});

const workerCmd1 = new command.local.Command("worker-cmd-1", {
    create: "printf \"%s\\n\" \"worker\"",
    environment: {
        APP_NAME: "worker",
        PORT: "3000",
    },
});

const webCmd1 = new command.local.Command("web-cmd-1", {
    create: "echo \"web ready\"",
    environment: {
        APP_NAME: "web",
        PORT: "8443",
        LOG_LEVEL: "debug",
    },
});

const gatewayCmd1 = new command.local.Command("gateway-cmd-1", {
    create: "echo \"gateway ready\"",
    environment: {
        APP_NAME: "gateway",
        PORT: "9090",
    },
});

const apiCmd1 = new command.local.Command("api-cmd-1", {
    create: "echo \"HealthCheck: api\"",
    environment: {
        APP_NAME: "api",
        REGION: "eu-west-1",
    },
});

const monitorCmd1 = new command.local.Command("monitor-cmd-1", {
    create: "echo \"Initializing monitor\"",
    environment: {
        APP_NAME: "monitor",
        PORT: "5000",
        REGION: "ap-southeast-1",
    },
});

const authCmd2 = new command.local.Command("auth-cmd-2", {
    create: "printf \"%s\\n\" \"auth\"",
    environment: {
        APP_NAME: "auth",
        PORT: "9090",
        LOG_LEVEL: "debug",
        REGION: "eu-west-1",
    },
});

const workerCmd2 = new command.local.Command("worker-cmd-2", {
    create: "echo \"worker ready\"",
    environment: {
        APP_NAME: "worker",
        PORT: "5000",
        REGION: "us-east-1",
    },
});

const webCmd2 = new command.local.Command("web-cmd-2", {
    create: "echo \"web ready\"",
    environment: {
        APP_NAME: "web",
        PORT: "9090",
        LOG_LEVEL: "info",
    },
    triggers: [webPass1.result],
});

