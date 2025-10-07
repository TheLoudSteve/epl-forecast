"""
Test Lambda Dead Letter Queue functionality

EPLF-60: Force a Lambda error to verify DLQ captures failed invocations
"""

import boto3
import json
import time

def test_lambda_dlq(function_name, environment='dev', region='us-west-2'):
    """
    Test DLQ by invoking Lambda with a payload that causes an error

    Args:
        function_name: Name of Lambda function to test (without env suffix)
        environment: Environment (dev/prod)
        region: AWS region (default: us-west-2)
    """
    lambda_client = boto3.client('lambda', region_name=region)
    sqs_client = boto3.client('sqs', region_name=region)

    full_function_name = f'{function_name}-{environment}'
    queue_name = f'epl-lambda-errors-{environment}'

    print(f"\n🧪 Testing DLQ for {full_function_name}\n")

    # Get queue URL
    try:
        queue_url_response = sqs_client.get_queue_url(QueueName=queue_name)
        queue_url = queue_url_response['QueueUrl']
        print(f"✅ Found DLQ: {queue_name}")
    except sqs_client.exceptions.QueueDoesNotExist:
        print(f"❌ ERROR: DLQ '{queue_name}' does not exist. Deploy CloudFormation stack first.")
        print(f"   Region: {region}")
        return False
    except Exception as e:
        print(f"❌ ERROR: Unexpected error getting queue URL: {e}")
        print(f"   Queue name: {queue_name}")
        print(f"   Region: {region}")
        return False

    # Check initial queue depth
    attrs = sqs_client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=['ApproximateNumberOfMessages']
    )
    initial_depth = int(attrs['Attributes']['ApproximateNumberOfMessages'])
    print(f"📊 Initial queue depth: {initial_depth}")

    # Invoke Lambda with payload designed to cause an error
    # This will force an unhandled exception in the Lambda
    error_payload = {
        "test_mode": "force_error",
        "error_type": "unhandled_exception",
        "timestamp": time.time()
    }

    print(f"\n🚀 Invoking {full_function_name} with error payload...")

    try:
        response = lambda_client.invoke(
            FunctionName=full_function_name,
            InvocationType='Event',  # Async invocation - DLQ only works with async
            Payload=json.dumps(error_payload)
        )

        print(f"✅ Lambda invoked (StatusCode: {response['StatusCode']})")
        print(f"   Note: Using async invocation - errors go to DLQ, not immediate response")

    except Exception as e:
        print(f"❌ Failed to invoke Lambda: {e}")
        return False

    # Wait for message to appear in DLQ (async processing takes a moment)
    print(f"\n⏳ Waiting 30 seconds for DLQ message to appear...")
    time.sleep(30)

    # Check final queue depth
    attrs = sqs_client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
    )
    final_depth = int(attrs['Attributes']['ApproximateNumberOfMessages'])
    in_flight = int(attrs['Attributes']['ApproximateNumberOfMessagesNotVisible'])

    print(f"\n📊 Final queue depth: {final_depth}")
    print(f"📊 Messages in flight: {in_flight}")

    if final_depth > initial_depth or in_flight > 0:
        print(f"\n✅ SUCCESS: DLQ captured the failed invocation!")
        print(f"   Messages added: {final_depth - initial_depth}")

        # Try to read the message
        messages = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5
        )

        if 'Messages' in messages:
            msg = messages['Messages'][0]
            print(f"\n📨 DLQ Message Preview:")
            print(f"   Message ID: {msg['MessageId']}")
            body = json.loads(msg['Body'])
            print(f"   Error Message: {body.get('errorMessage', 'N/A')}")
            print(f"   Request ID: {body.get('requestContext', {}).get('requestId', 'N/A')}")

            # Don't delete the message - leave it for inspection
            print(f"\n💡 Message left in queue for inspection")
            print(f"   View in AWS Console: SQS > {queue_name}")

        return True
    else:
        print(f"\n⚠️  WARNING: No new messages in DLQ")
        print(f"   Possible reasons:")
        print(f"   1. Lambda code doesn't raise unhandled exceptions")
        print(f"   2. DLQ not properly configured on Lambda")
        print(f"   3. Need to wait longer for async processing")
        print(f"\n💡 Check CloudWatch Logs for the Lambda execution:")
        print(f"   aws logs tail /aws/lambda/{full_function_name} --follow")
        return False


def main():
    """Test DLQ for all Lambda functions"""
    import argparse

    parser = argparse.ArgumentParser(description='Test Lambda Dead Letter Queue')
    parser.add_argument('--function', '-f',
                       choices=['epl-api-handler', 'epl-scheduled-fetcher',
                               'epl-live-fetcher', 'epl-schedule-manager'],
                       default='epl-api-handler',
                       help='Lambda function to test')
    parser.add_argument('--env', '-e',
                       choices=['dev', 'prod'],
                       default='dev',
                       help='Environment')

    args = parser.parse_args()

    print("=" * 70)
    print("Lambda Dead Letter Queue Test (EPLF-60)")
    print("=" * 70)

    success = test_lambda_dlq(args.function, args.env)

    if success:
        print("\n✅ DLQ test PASSED")
        exit(0)
    else:
        print("\n❌ DLQ test FAILED or INCONCLUSIVE")
        exit(1)


if __name__ == "__main__":
    main()
