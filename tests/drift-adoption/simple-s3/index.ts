import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

const bucket = new aws.s3.Bucket("test-bucket", {
    forceDestroy: true,
});

export const bucketName = bucket.id;
