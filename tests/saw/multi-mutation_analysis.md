## Case 1

```
[
    {
        "rule": "binop-int-replace",
        "function": "s2n_blob_zero",
        "instruction": 4,
        "package": {
            "repl": "Or",
            "swap": false
        }
    },
    {
        "rule": "const-replace",
        "function": "s2n_socket_quickack",
        "instruction": 17,
        "package": {
            "action": "set-minus-2",
            "operand": 1
        }
    },
    {
        "rule": "branch-swap",
        "function": "s2n_blob_zero",
        "instruction": 7,
        "package": {}
    }
]
```

Apply only the first mutation:

```
[04:06:19.676] Loading file "/home/r2ji/draft_mutation/s2n-tls/tests/saw/verify_drbg.saw"
[04:06:19.677] Loading file "/home/r2ji/draft_mutation/s2n-tls/tests/saw/spec/DRBG/DRBG.saw"

[04:06:23.073] Assume override getenv
[04:06:23.096] Assume override EVP_aes_128_ecb
[04:06:23.125] Assume override EVP_CIPHER_CTX_new
[04:06:23.145] Assume override EVP_CIPHER_CTX_free
[04:06:23.202] Assume override EVP_CIPHER_CTX_reset
[04:06:23.237] Assume override EVP_CIPHER_CTX_key_length
[04:06:23.285] Assume override EVP_EncryptInit_ex
[04:06:23.327] Assume override EVP_EncryptInit_ex
[04:06:23.437] Assume override EVP_EncryptUpdate
[04:06:23.461] Assume override s2n_cpu_supports_rdrand
[04:06:23.559] Assume override s2n_get_public_random_data
[04:06:23.661] Assume override s2n_get_seed_entropy
[04:06:23.760] Assume override s2n_get_mix_entropy
[04:06:23.857] Verifying s2n_blob_zero ...
[04:06:23.857] Simulating s2n_blob_zero ...
[04:06:23.859] Stack trace:
"include" (/home/r2ji/draft_mutation/s2n-tls/tests/saw/verify_drbg.saw:1:1-1:8):
"crucible_llvm_verify" (/home/r2ji/draft_mutation/s2n-tls/tests/saw/spec/DRBG/DRBG.saw:387:18-387:38):
at /home/r2ji/draft_mutation/s2n-tls/tests/saw/spec/DRBG/DRBG.saw:253:5
error when loading through pointer that appeared in the override's points-to precondition(s):
Precondition:
  Pointer: concrete pointer: allocation = 2028, offset = 0
  Pointee: let { x@1 = Prelude.Vec 8 Prelude.Bool
      }
   in Cryptol.ecZero (Prelude.Vec 16 x@1)
        (Cryptol.PZeroSeq (Cryptol.TCNum 16) x@1
           (Cryptol.PZeroSeqBool (Cryptol.TCNum 8))) : [16][8]

  Assertion made at: /home/r2ji/draft_mutation/s2n-tls/tests/saw/spec/DRBG/DRBG.saw:253:5
Failure reason: 
  When reading through pointer: (2028, 0x0:[64])
  in the  postcondition of an override
  Tried to read something of size: 16
  And type: [16 x i8]
  Found 1 possibly matching allocation(s):
  - HeapAlloc 2028 0x10:[64] Mutable 1-byte-aligned /home/r2ji/draft_mutation/s2n-tls/tests/saw/spec/DRBG/DRBG.saw:99:14

```


[Original Code](https://github.com/aws/s2n-tls/blob/eff95749338b8b643e6555e5a98c7538dc0082d8/utils/s2n_blob.c#L50)

The root function is blob_zero_spec

The function call process:

blob_zero_spec --- POSIX_PRECONDITION(s2n_blob_validate(b))
               |-- POSIX_GUARD_RESULT(__S2N_ENSURE_PRECONDITION((result))) 
                    |-- __S2N_ENSURE(s2n_result_is_ok(result), return S2N_FAILURE)
#define __S2N_ENSURE( cond, action ) do {if ( !(cond) ) { action; }} while (0)

```
if(!(s2n_result_is_ok(result))),
```


Original bitcode that is mutated

```
  tail call void @llvm.dbg.value(metadata %struct.s2n_blob* %0, i64 0, metadata !43791, metadata !43797), !dbg !43798
  %2 = tail call i32 @s2n_blob_validate(%struct.s2n_blob* %0), !dbg !43799
  %3 = tail call zeroext i1 @s2n_result_is_ok(i32 %2) #16, !dbg !43803
  %4 = xor i1 %3, true, !dbg !43805
  %5 = sext i1 %4 to i32, !dbg !43805
  %6 = tail call zeroext i1 @s2n_result_is_ok(i32 %5) #16, !dbg !43807
  br i1 %6, label %7, label %31, !dbg !43807

```

Change Xor to Or


First understand what is the spec doing here:
```
let blob_zero_spec n = do {
    (p, datap) <- alloc_blob n;
    crucible_execute_func [p];
    crucible_points_to datap (tm {{ zero : [n][8] }});
    crucible_return (tm {{ 0 : [32] }});
};

```
it is a Hoare-style pre/post
specification. The interface sets up symbolic memory (the pre-condition), sym-
bolically executes the function (crucible_execute_func), and then checks that
the resulting symbolic memory contains the correct values (the post-condition)
```

For crucible

```
Crucible
is the intermediate language for symbolic execution used by SAW. Internally,
the semantics of LLVM, x86, and other SAW input languages are defined by
translation to Crucible
```
[Some explanation on how to understand spec](https://assets.amazon.science/4e/23/177acd514c799204ae22f98e193d/verified-cryptographic-code-for-everybody.pdf)
