import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

const bucketNames = ["logs-bucket", "backup-bucket"];

const buckets: { [key: string]: aws.s3.Bucket } = {};
const bucketIds: { [key: string]: pulumi.Output<string> } = {};

for (const name of bucketNames) {
    buckets[name] = new aws.s3.Bucket(name, {
        forceDestroy: true,
    });
    bucketIds[name] = buckets[name].id;
}

export const logsBucketId = buckets["logs-bucket"].id;
export const backupBucketId = buckets["backup-bucket"].id;
export const bucketCount = bucketNames.length;
