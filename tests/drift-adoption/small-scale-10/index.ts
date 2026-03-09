import * as pulumi from "@pulumi/pulumi";
import * as random from "@pulumi/random";
import * as command from "@pulumi/command";
import * as tls from "@pulumi/tls";

const randomStr0 = new random.RandomString("random-str-0", {
    length: 16,
    special: false,
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

const cmd0 = new command.local.Command("cmd-0", {
    create: "echo resource-0",
});

const cmd1 = new command.local.Command("cmd-1", {
    create: "echo resource-1",
});

const cmd2 = new command.local.Command("cmd-2", {
    create: "echo resource-2",
});

const cmd3 = new command.local.Command("cmd-3", {
    create: "echo resource-3",
});

const tlsKey0 = new tls.PrivateKey("tls-key-0", {
    algorithm: "RSA",
    rsaBits: 2048,
});

const tlsKey1 = new tls.PrivateKey("tls-key-1", {
    algorithm: "RSA",
    rsaBits: 2048,
});
