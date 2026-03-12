import * as pulumi from "@pulumi/pulumi";
import * as random from "@pulumi/random";
import * as command from "@pulumi/command";
import * as tls from "@pulumi/tls";

const webCaKey = new tls.PrivateKey("web-ca-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const webCaCert = new tls.SelfSignedCert("web-ca-cert", {
    privateKeyPem: webCaKey.privateKeyPem,
    subject: {
        organization: "Acme Corp",
        commonName: "Web CA",
        country: "US",
    },
    validityPeriodHours: 43800,
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
        organization: "Acme Corp",
    },
    dnsNames: ["web.example.com", "*.web.example.com"],
});

const webServerCert = new tls.LocallySignedCert("web-server-cert", {
    certRequestPem: webServerCsr.certRequestPem,
    caPrivateKeyPem: webCaKey.privateKeyPem,
    caCertPem: webCaCert.certPem,
    validityPeriodHours: 43800,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const cacheCaKey = new tls.PrivateKey("cache-ca-key", {
    algorithm: "RSA",
    rsaBits: 4096,
});

const cacheCaCert = new tls.SelfSignedCert("cache-ca-cert", {
    privateKeyPem: cacheCaKey.privateKeyPem,
    subject: {
        organization: "Acme Corp",
        commonName: "Cache CA",
        country: "GB",
    },
    validityPeriodHours: 43800,
    allowedUses: ["cert_signing", "crl_signing"],
    isCaCertificate: true,
});

const cacheServerKey = new tls.PrivateKey("cache-server-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const cacheServerCsr = new tls.CertRequest("cache-server-csr", {
    privateKeyPem: cacheServerKey.privateKeyPem,
    subject: {
        commonName: "cache.example.com",
        organization: "Acme Corp",
    },
    dnsNames: ["cache.example.com", "*.cache.example.com"],
});

const cacheServerCert = new tls.LocallySignedCert("cache-server-cert", {
    certRequestPem: cacheServerCsr.certRequestPem,
    caPrivateKeyPem: cacheCaKey.privateKeyPem,
    caCertPem: cacheCaCert.certPem,
    validityPeriodHours: 43800,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const monitorCaKey = new tls.PrivateKey("monitor-ca-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const monitorCaCert = new tls.SelfSignedCert("monitor-ca-cert", {
    privateKeyPem: monitorCaKey.privateKeyPem,
    subject: {
        organization: "Fabrikam Inc",
        commonName: "Monitor CA",
        country: "GB",
    },
    validityPeriodHours: 26280,
    allowedUses: ["cert_signing", "crl_signing"],
    isCaCertificate: true,
});

const monitorServerKey = new tls.PrivateKey("monitor-server-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const monitorServerCsr = new tls.CertRequest("monitor-server-csr", {
    privateKeyPem: monitorServerKey.privateKeyPem,
    subject: {
        commonName: "monitor.example.com",
        organization: "Fabrikam Inc",
    },
    dnsNames: ["monitor.example.com", "*.monitor.example.com"],
});

const monitorServerCert = new tls.LocallySignedCert("monitor-server-cert", {
    certRequestPem: monitorServerCsr.certRequestPem,
    caPrivateKeyPem: monitorCaKey.privateKeyPem,
    caCertPem: monitorCaCert.certPem,
    validityPeriodHours: 26280,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const workerCaKey = new tls.PrivateKey("worker-ca-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const workerCaCert = new tls.SelfSignedCert("worker-ca-cert", {
    privateKeyPem: workerCaKey.privateKeyPem,
    subject: {
        organization: "Contoso Ltd",
        commonName: "Worker CA",
        country: "DE",
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
        organization: "Contoso Ltd",
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

const apiCaKey = new tls.PrivateKey("api-ca-key", {
    algorithm: "RSA",
    rsaBits: 4096,
});

const apiCaCert = new tls.SelfSignedCert("api-ca-cert", {
    privateKeyPem: apiCaKey.privateKeyPem,
    subject: {
        organization: "Contoso Ltd",
        commonName: "Api CA",
        country: "JP",
    },
    validityPeriodHours: 26280,
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
        organization: "Contoso Ltd",
    },
    dnsNames: ["api.example.com", "*.api.example.com"],
});

const apiServerCert = new tls.LocallySignedCert("api-server-cert", {
    certRequestPem: apiServerCsr.certRequestPem,
    caPrivateKeyPem: apiCaKey.privateKeyPem,
    caCertPem: apiCaCert.certPem,
    validityPeriodHours: 26280,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const gatewayCaKey = new tls.PrivateKey("gateway-ca-key", {
    algorithm: "RSA",
    rsaBits: 4096,
});

const gatewayCaCert = new tls.SelfSignedCert("gateway-ca-cert", {
    privateKeyPem: gatewayCaKey.privateKeyPem,
    subject: {
        organization: "Northwind Traders",
        commonName: "Gateway CA",
        country: "GB",
    },
    validityPeriodHours: 43800,
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
        organization: "Northwind Traders",
    },
    dnsNames: ["gateway.example.com", "*.gateway.example.com"],
});

const gatewayServerCert = new tls.LocallySignedCert("gateway-server-cert", {
    certRequestPem: gatewayServerCsr.certRequestPem,
    caPrivateKeyPem: gatewayCaKey.privateKeyPem,
    caCertPem: gatewayCaCert.certPem,
    validityPeriodHours: 43800,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const webStr = new random.RandomString("web-str", {
    length: 8,
    special: true,
    minLower: 4,
    minUpper: 2,
    minNumeric: 1,
});

const cachePass = new random.RandomPassword("cache-pass", {
    length: 24,
    special: true,
});

const monitorInt = new random.RandomInteger("monitor-int", {
    min: 1,
    max: 10000,
});

const workerId = new random.RandomId("worker-id", {
    byteLength: 4,
});

const apiPet = new random.RandomPet("api-pet", {
    length: 2,
});

const gatewayShuffle = new random.RandomShuffle("gateway-shuffle", {
    inputs: ["alpha", "beta", "gamma", "delta", "epsilon"],
});

const authUuid = new random.RandomUuid("auth-uuid", {
});

const dbStr1 = new random.RandomString("db-str-1", {
    length: 24,
    special: false,
});

const webPass1 = new random.RandomPassword("web-pass-1", {
    length: 48,
    special: true,
    keepers: { ref: dbStr1.result },
});

const cacheInt1 = new random.RandomInteger("cache-int-1", {
    min: 1,
    max: 10000,
});

const monitorId1 = new random.RandomId("monitor-id-1", {
    byteLength: 8,
    prefix: "env-",
});

const workerPet1 = new random.RandomPet("worker-pet-1", {
    length: 4,
});

const apiShuffle1 = new random.RandomShuffle("api-shuffle-1", {
    inputs: ["alpha", "beta", "gamma", "delta", "epsilon"],
    resultCount: 5,
});

const gatewayUuid1 = new random.RandomUuid("gateway-uuid-1", {
});

const authStr2 = new random.RandomString("auth-str-2", {
    length: 24,
    special: true,
    minLower: 3,
    minNumeric: 1,
});

const dbPass2 = new random.RandomPassword("db-pass-2", {
    length: 24,
    special: true,
    overrideSpecial: "!@#$%^&*()",
});

const webInt2 = new random.RandomInteger("web-int-2", {
    min: 100,
    max: 999,
});

const cacheId2 = new random.RandomId("cache-id-2", {
    byteLength: 8,
    prefix: "app-",
});

const monitorPet2 = new random.RandomPet("monitor-pet-2", {
    length: 4,
    separator: "-",
});

const workerShuffle2 = new random.RandomShuffle("worker-shuffle-2", {
    inputs: ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
});

const apiUuid2 = new random.RandomUuid("api-uuid-2", {
});

const gatewayStr3 = new random.RandomString("gateway-str-3", {
    length: 16,
    special: true,
});

const authPass3 = new random.RandomPassword("auth-pass-3", {
    length: 48,
    special: true,
    minUpper: 5,
    overrideSpecial: "._-+",
});

const dbInt3 = new random.RandomInteger("db-int-3", {
    min: 1,
    max: 100,
});

const webId3 = new random.RandomId("web-id-3", {
    byteLength: 4,
});

const cachePet3 = new random.RandomPet("cache-pet-3", {
    length: 2,
    separator: "-",
    prefix: "prod",
});

const monitorShuffle3 = new random.RandomShuffle("monitor-shuffle-3", {
    inputs: ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
    resultCount: 4,
});

const workerUuid3 = new random.RandomUuid("worker-uuid-3", {
});

const apiStr4 = new random.RandomString("api-str-4", {
    length: 8,
    special: false,
});

const gatewayPass4 = new random.RandomPassword("gateway-pass-4", {
    length: 24,
    special: true,
    keepers: { ref: workerId.hex },
});

const authInt4 = new random.RandomInteger("auth-int-4", {
    min: 1,
    max: 1000,
});

const dbId4 = new random.RandomId("db-id-4", {
    byteLength: 8,
    prefix: "res-",
});

const webPet4 = new random.RandomPet("web-pet-4", {
    length: 3,
});

const cacheShuffle4 = new random.RandomShuffle("cache-shuffle-4", {
    inputs: ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
    resultCount: 1,
});

const monitorUuid4 = new random.RandomUuid("monitor-uuid-4", {
});

const workerStr5 = new random.RandomString("worker-str-5", {
    length: 32,
    special: false,
    minLower: 3,
    minUpper: 1,
});

const apiPass5 = new random.RandomPassword("api-pass-5", {
    length: 32,
    special: true,
    minLower: 2,
    overrideSpecial: "!@#$%^&*()",
    keepers: { ref: cachePet3.id },
});

const gatewayInt5 = new random.RandomInteger("gateway-int-5", {
    min: 1,
    max: 100,
});

const authId5 = new random.RandomId("auth-id-5", {
    byteLength: 4,
});

const dbPet5 = new random.RandomPet("db-pet-5", {
    length: 3,
    separator: "_",
    prefix: "staging",
});

const webShuffle5 = new random.RandomShuffle("web-shuffle-5", {
    inputs: ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
    resultCount: 3,
});

const cacheUuid5 = new random.RandomUuid("cache-uuid-5", {
});

const monitorStr6 = new random.RandomString("monitor-str-6", {
    length: 64,
    special: true,
    minLower: 1,
    minNumeric: 3,
});

const workerPass6 = new random.RandomPassword("worker-pass-6", {
    length: 24,
    special: true,
    minLower: 5,
    minUpper: 3,
});

const apiInt6 = new random.RandomInteger("api-int-6", {
    min: 100,
    max: 999,
});

const webCmd = new command.local.Command("web-cmd", {
    create: "date +%s",
    environment: {
        APP_NAME: "web",
        LOG_LEVEL: "debug",
    },
});

const cacheCmd = new command.local.Command("cache-cmd", {
    create: "printf \"%s\\n\" \"cache\"",
    environment: {
        APP_NAME: "cache",
        PORT: "3000",
        REGION: "ap-southeast-1",
    },
    triggers: [apiPass5.result],
});

const monitorCmd = new command.local.Command("monitor-cmd", {
    create: "echo \"monitor ready\"",
    environment: {
        APP_NAME: "monitor",
        PORT: "9090",
        REGION: "eu-west-1",
    },
});

const workerCmd = new command.local.Command("worker-cmd", {
    create: "echo \"HealthCheck: worker\"",
    environment: {
        APP_NAME: "worker",
    },
});

const apiCmd = new command.local.Command("api-cmd", {
    create: "date +%s",
    environment: {
        APP_NAME: "api",
        PORT: "8443",
        REGION: "ap-southeast-1",
    },
});

const gatewayCmd = new command.local.Command("gateway-cmd", {
    create: "date +%s",
    environment: {
        APP_NAME: "gateway",
        PORT: "3000",
        LOG_LEVEL: "debug",
    },
    triggers: [webShuffle5.results],
});

const authCmd = new command.local.Command("auth-cmd", {
    create: "echo \"Initializing auth\"",
    environment: {
        APP_NAME: "auth",
        LOG_LEVEL: "error",
        REGION: "us-east-1",
    },
});

const dbCmd = new command.local.Command("db-cmd", {
    create: "printf \"%s\\n\" \"db\"",
    environment: {
        APP_NAME: "db",
        PORT: "3000",
    },
});

const webCmd1 = new command.local.Command("web-cmd-1", {
    create: "echo \"Initializing web\"",
    environment: {
        APP_NAME: "web",
        LOG_LEVEL: "info",
    },
});

const cacheCmd1 = new command.local.Command("cache-cmd-1", {
    create: "echo \"Initializing cache\"",
    environment: {
        APP_NAME: "cache",
        PORT: "8080",
        LOG_LEVEL: "warn",
        REGION: "eu-west-1",
    },
});

const monitorCmd1 = new command.local.Command("monitor-cmd-1", {
    create: "echo \"HealthCheck: monitor\"",
    environment: {
        APP_NAME: "monitor",
        LOG_LEVEL: "debug",
        REGION: "ap-southeast-1",
    },
});

const workerCmd1 = new command.local.Command("worker-cmd-1", {
    create: "printf \"%s\\n\" \"worker\"",
    environment: {
        APP_NAME: "worker",
        PORT: "5000",
        REGION: "eu-west-1",
    },
});

const apiCmd1 = new command.local.Command("api-cmd-1", {
    create: "date +%s",
    environment: {
        APP_NAME: "api",
        PORT: "3000",
    },
    triggers: [cacheShuffle4.results],
});

const gatewayCmd1 = new command.local.Command("gateway-cmd-1", {
    create: "echo \"gateway ready\"",
    environment: {
        APP_NAME: "gateway",
        PORT: "9090",
        REGION: "ap-southeast-1",
    },
});

const authCmd1 = new command.local.Command("auth-cmd-1", {
    create: "date +%s",
    environment: {
        APP_NAME: "auth",
        PORT: "8443",
        LOG_LEVEL: "error",
        REGION: "eu-west-1",
    },
    triggers: [cacheId2.hex],
});

const dbCmd1 = new command.local.Command("db-cmd-1", {
    create: "date +%s",
    environment: {
        APP_NAME: "db",
        PORT: "8080",
    },
});

const webCmd2 = new command.local.Command("web-cmd-2", {
    create: "date +%s",
    environment: {
        APP_NAME: "web",
        PORT: "8080",
        LOG_LEVEL: "info",
        REGION: "eu-west-1",
    },
    triggers: [authPass3.result],
});

const cacheCmd2 = new command.local.Command("cache-cmd-2", {
    create: "echo \"Initializing cache\"",
    environment: {
        APP_NAME: "cache",
        PORT: "9090",
        REGION: "ap-southeast-1",
    },
});

const monitorCmd2 = new command.local.Command("monitor-cmd-2", {
    create: "echo \"HealthCheck: monitor\"",
    environment: {
        APP_NAME: "monitor",
    },
    triggers: [authId5.hex],
});

const workerCmd2 = new command.local.Command("worker-cmd-2", {
    create: "echo \"Initializing worker\"",
    environment: {
        APP_NAME: "worker",
        LOG_LEVEL: "warn",
    },
});

const apiCmd2 = new command.local.Command("api-cmd-2", {
    create: "printf \"%s\\n\" \"api\"",
    environment: {
        APP_NAME: "api",
        LOG_LEVEL: "error",
    },
    triggers: [webPass1.result],
});

const gatewayCmd2 = new command.local.Command("gateway-cmd-2", {
    create: "echo \"gateway ready\"",
    environment: {
        APP_NAME: "gateway",
        PORT: "8443",
        REGION: "eu-west-1",
    },
});

const authCmd2 = new command.local.Command("auth-cmd-2", {
    create: "printf \"%s\\n\" \"auth\"",
    environment: {
        APP_NAME: "auth",
        PORT: "3000",
        LOG_LEVEL: "debug",
    },
});

const dbCmd2 = new command.local.Command("db-cmd-2", {
    create: "echo \"HealthCheck: db\"",
    environment: {
        APP_NAME: "db",
        PORT: "8080",
        REGION: "eu-west-1",
    },
});

const webCmd3 = new command.local.Command("web-cmd-3", {
    create: "date +%s",
    environment: {
        APP_NAME: "web",
    },
});

