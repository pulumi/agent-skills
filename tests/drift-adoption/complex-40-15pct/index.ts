import * as pulumi from "@pulumi/pulumi";
import * as random from "@pulumi/random";
import * as command from "@pulumi/command";
import * as tls from "@pulumi/tls";

const dbCaKey = new tls.PrivateKey("db-ca-key", {
    algorithm: "RSA",
    rsaBits: 4096,
});

const dbCaCert = new tls.SelfSignedCert("db-ca-cert", {
    privateKeyPem: dbCaKey.privateKeyPem,
    subject: {
        organization: "Fabrikam Inc",
        commonName: "Db CA",
        country: "JP",
    },
    validityPeriodHours: 17520,
    allowedUses: ["cert_signing", "crl_signing"],
    isCaCertificate: true,
});

const dbServerKey = new tls.PrivateKey("db-server-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const dbServerCsr = new tls.CertRequest("db-server-csr", {
    privateKeyPem: dbServerKey.privateKeyPem,
    subject: {
        commonName: "db.example.com",
        organization: "Fabrikam Inc",
    },
    dnsNames: ["db.example.com", "*.db.example.com"],
});

const dbServerCert = new tls.LocallySignedCert("db-server-cert", {
    certRequestPem: dbServerCsr.certRequestPem,
    caPrivateKeyPem: dbCaKey.privateKeyPem,
    caCertPem: dbCaCert.certPem,
    validityPeriodHours: 17520,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const workerCaKey = new tls.PrivateKey("worker-ca-key", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const workerCaCert = new tls.SelfSignedCert("worker-ca-cert", {
    privateKeyPem: workerCaKey.privateKeyPem,
    subject: {
        organization: "Acme Corp",
        commonName: "Worker CA",
        country: "GB",
    },
    validityPeriodHours: 8760,
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
        organization: "Acme Corp",
    },
    dnsNames: ["worker.example.com", "*.worker.example.com"],
});

const workerServerCert = new tls.LocallySignedCert("worker-server-cert", {
    certRequestPem: workerServerCsr.certRequestPem,
    caPrivateKeyPem: workerCaKey.privateKeyPem,
    caCertPem: workerCaCert.certPem,
    validityPeriodHours: 8760,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const authCaKey = new tls.PrivateKey("auth-ca-key", {
    algorithm: "RSA",
    rsaBits: 4096,
});

const authCaCert = new tls.SelfSignedCert("auth-ca-cert", {
    privateKeyPem: authCaKey.privateKeyPem,
    subject: {
        organization: "Acme Corp",
        commonName: "Auth CA",
        country: "GB",
    },
    validityPeriodHours: 87600,
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
    validityPeriodHours: 87600,
    allowedUses: ["digital_signature", "key_encipherment", "server_auth"],
});

const dbStr = new random.RandomString("db-str", {
    length: 64,
    special: false,
    minLower: 3,
    minUpper: 1,
});

const workerPass = new random.RandomPassword("worker-pass", {
    length: 16,
    special: true,
    minUpper: 4,
    overrideSpecial: "!@#$%",
});

const authInt = new random.RandomInteger("auth-int", {
    min: 1024,
    max: 65535,
});

const apiId = new random.RandomId("api-id", {
    byteLength: 4,
});

const webPet = new random.RandomPet("web-pet", {
    length: 4,
});

const dbShuffle = new random.RandomShuffle("db-shuffle", {
    inputs: ["small", "medium", "large", "xlarge"],
});

const workerUuid = new random.RandomUuid("worker-uuid", {
});

const authStr1 = new random.RandomString("auth-str-1", {
    length: 16,
    special: false,
    minUpper: 2,
});

const apiPass1 = new random.RandomPassword("api-pass-1", {
    length: 16,
    special: true,
    minLower: 6,
    minUpper: 3,
});

const webInt1 = new random.RandomInteger("web-int-1", {
    min: 1,
    max: 10000,
});

const dbId1 = new random.RandomId("db-id-1", {
    byteLength: 8,
    prefix: "res-",
});

const workerPet1 = new random.RandomPet("worker-pet-1", {
    length: 4,
    prefix: "staging",
});

const authShuffle1 = new random.RandomShuffle("auth-shuffle-1", {
    inputs: ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
});

const apiUuid1 = new random.RandomUuid("api-uuid-1", {
});

const webStr2 = new random.RandomString("web-str-2", {
    length: 16,
    special: false,
    minLower: 4,
    minUpper: 4,
    minNumeric: 1,
});

const dbPass2 = new random.RandomPassword("db-pass-2", {
    length: 48,
    special: true,
});

const dbCmd = new command.local.Command("db-cmd", {
    create: "date +%s",
    environment: {
        APP_NAME: "db",
        LOG_LEVEL: "warn",
        REGION: "us-east-1",
    },
    triggers: [dbShuffle.results],
});

const workerCmd = new command.local.Command("worker-cmd", {
    create: "echo \"Initializing worker\"",
    environment: {
        APP_NAME: "worker",
        LOG_LEVEL: "error",
    },
});

const authCmd = new command.local.Command("auth-cmd", {
    create: "date +%s",
    environment: {
        APP_NAME: "auth",
        PORT: "5000",
        LOG_LEVEL: "error",
    },
    triggers: [dbShuffle.results],
});

const apiCmd = new command.local.Command("api-cmd", {
    create: "echo \"api ready\"",
    environment: {
        APP_NAME: "api",
        PORT: "3000",
        LOG_LEVEL: "error",
    },
});

const webCmd = new command.local.Command("web-cmd", {
    create: "date +%s",
    environment: {
        APP_NAME: "web",
        PORT: "3000",
    },
});

const dbCmd1 = new command.local.Command("db-cmd-1", {
    create: "printf \"%s\\n\" \"db\"",
    environment: {
        APP_NAME: "db",
        PORT: "9090",
        LOG_LEVEL: "info",
    },
    triggers: [workerPet1.id],
});

const workerCmd1 = new command.local.Command("worker-cmd-1", {
    create: "date +%s",
    environment: {
        APP_NAME: "worker",
        LOG_LEVEL: "debug",
    },
    triggers: [apiId.hex],
});

const authCmd1 = new command.local.Command("auth-cmd-1", {
    create: "echo \"auth ready\"",
    environment: {
        APP_NAME: "auth",
        REGION: "ap-southeast-1",
    },
});

const apiCmd1 = new command.local.Command("api-cmd-1", {
    create: "echo \"api ready\"",
    environment: {
        APP_NAME: "api",
        PORT: "9090",
        REGION: "ap-southeast-1",
    },
    triggers: [dbStr.result],
});

