import * as pulumi from "@pulumi/pulumi";
import * as random from "@pulumi/random";
import * as command from "@pulumi/command";
import * as tls from "@pulumi/tls";

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
    dnsNames: ["worker.example.com", "*.worker.example.com", "extra.worker.example.com"],
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
    length: 8,
    special: true,
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
    min: 1056,
    max: 65562,
});

const apiId = new random.RandomId("api-id", {
    byteLength: 4,
});

const webPet = new random.RandomPet("web-pet", {
    length: 4,
});

const dbShuffle = new random.RandomShuffle("db-shuffle", {
    inputs: ["small", "medium", "large", "xlarge"],
    resultCount: 1,
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
    resultCount: 1,
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
        DRIFT: "true",
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
        DRIFT: "true",
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

const extra0 = new random.RandomString("extra-0", {
    length: 24,
    special: true,
});

const extra1 = new random.RandomPassword("extra-1", {
    length: 32,
    special: true,
});

const extra2 = new random.RandomId("extra-2", {
    byteLength: 16,
});

const extra3 = new command.local.Command("extra-3", {
    create: "echo \"extra-resource-3\"",
    environment: {
        APP_NAME: "extra",
        INDEX: "3",
    },
});

const extra4 = new random.RandomString("extra-4", {
    length: 24,
    special: true,
});

const extra5 = new random.RandomPassword("extra-5", {
    length: 32,
    special: true,
});

