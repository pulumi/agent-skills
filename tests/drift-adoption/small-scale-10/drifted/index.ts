import * as pulumi from "@pulumi/pulumi";
import * as random from "@pulumi/random";
import * as command from "@pulumi/command";
import * as tls from "@pulumi/tls";

// DRIFT: property change (length 16->32, special false->true) -> replace
const randomStr0 = new random.RandomString("random-str-0", {
    length: 32,
    special: true,
});

const randomStr1 = new random.RandomString("random-str-1", {
    length: 16,
    special: false,
});

const randomStr2 = new random.RandomString("random-str-2", {
    length: 16,
    special: false,
});

const randomStr3 = new random.RandomString("random-str-3", {
    length: 16,
    special: false,
});

// DRIFT: property change (add environment var) -> update
const cmd0 = new command.local.Command("cmd-0", {
    create: "echo resource-0-modified",
    environment: { DRIFT: "true" },
});

const cmd1 = new command.local.Command("cmd-1", {
    create: "echo resource-1",
});

const cmd2 = new command.local.Command("cmd-2", {
    create: "echo resource-2",
});

// DRIFT: cmd3 deleted from drifted code -> create on preview
// (cmd3 exists in state but not in drifted code)

// DRIFT: property change (RSA->ECDSA) -> replace
const tlsKey0 = new tls.PrivateKey("tls-key-0", {
    algorithm: "ECDSA",
    ecdsaCurve: "P256",
});

const tlsKey1 = new tls.PrivateKey("tls-key-1", {
    algorithm: "RSA",
    rsaBits: 2048,
});

// DRIFT: extra resource only in drifted code -> delete on preview
const randomStrExtra0 = new random.RandomString("random-str-extra-0", {
    length: 16,
    special: false,
});
