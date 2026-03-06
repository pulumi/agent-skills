import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";

const bucketA = new aws.s3.Bucket("bucket-a", {
    forceDestroy: true,
});

const bucketB = new aws.s3.Bucket("bucket-b", {
    forceDestroy: true,
});

const bucketC = new aws.s3.Bucket("bucket-c", {
    forceDestroy: true,
});

export const bucketNameA = bucketA.id;
export const bucketNameB = bucketB.id;
export const bucketNameC = bucketC.id;
