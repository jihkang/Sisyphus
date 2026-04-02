# Repro

## Preconditions

- Test environment with retry enabled

## Repro Steps

1. Send unicode payload
2. Trigger retry flow

## Observed Result

- Parser fails with invalid state

## Expected Result

- Payload is retried and parsed successfully

## Regression Test Target

- Add regression test for unicode payload retry flow
