# CloudShell Diagnostics

Commands for checking AMIE deployments from AWS CloudShell. Run these in the us-west-2 region (set via the region selector in the CloudShell top bar).

---

## Stack Status and Outputs

Shows the current stack state and all output values (API URLs, bucket names).

```bash
aws cloudformation describe-stacks --stack-name amie \
  --query 'Stacks[0].{Status:StackStatus,Outputs:Outputs}' \
  --output table
```

## Lambda Functions in the Stack

Lists every Lambda function created by the SAM template, its physical name, and deployment status.

```bash
aws cloudformation list-stack-resources --stack-name amie \
  --query "StackResourceSummaries[?ResourceType=='AWS::Lambda::Function'].[LogicalResourceId,PhysicalResourceId,ResourceStatus]" \
  --output table
```

## Lambda Function Details

Shows state, last modified time, timeout, and memory for each agent Lambda.

```bash
for fn in amie-api amie-worker amie-idca amie-naa amie-aa; do
  echo "--- $fn ---"
  aws lambda get-function --function-name $fn \
    --query 'Configuration.{State:State,LastModified:LastModified,Timeout:Timeout,Memory:MemorySize}' \
    --output table 2>/dev/null || echo "  not found"
done
```

## Recent Errors (Worker Lambda, Last Hour)

Filters CloudWatch logs for ERROR entries in the worker Lambda.

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/amie-worker \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s000 2>/dev/null || date -v-1H +%s000) \
  --query 'events[].[timestamp,message]' \
  --output text | head -20
```

Replace `amie-worker` with any of the other log group names to check a specific agent:

- `/aws/lambda/amie-api`
- `/aws/lambda/amie-idca`
- `/aws/lambda/amie-naa`
- `/aws/lambda/amie-aa`

## All Resources in the Stack

Full inventory of every AWS resource the stack created.

```bash
aws cloudformation list-stack-resources --stack-name amie \
  --query 'StackResourceSummaries[].[ResourceType,LogicalResourceId,ResourceStatus]' \
  --output table
```

## Recent Deployments

Shows stack events from the most recent deployment.

```bash
aws cloudformation describe-stack-events --stack-name amie \
  --query 'StackEvents[?ResourceStatus!=`CREATE_COMPLETE` && ResourceStatus!=`UPDATE_COMPLETE`].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' \
  --output table | head -40
```

## S3 Bucket Contents

Check what's in the manuscript and task buckets.

```bash
# List recent uploads
aws s3 ls s3://amie-manuscripts-257247532024-us-west-2/uploads/ --recursive | tail -10

# List recent tasks
aws s3 ls s3://amie-tasks-257247532024-us-west-2/tasks/ --recursive | tail -10

# Read a specific task's state
aws s3 cp s3://amie-tasks-257247532024-us-west-2/tasks/<TASK_ID>.json - | python3 -m json.tool
```
