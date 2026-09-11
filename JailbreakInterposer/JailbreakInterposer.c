//
// Copyright © 2021 osy. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

#include <TargetConditionals.h>
#if !TARGET_OS_SIMULATOR
#include <IOKit/IOKitLib.h>
#include <unistd.h>

/* Recent iPhoneOS SDKs (Xcode 26) declare IOServiceAuthorize as unavailable on
 * iOS, which makes naming it a hard compile error (the availability diagnostic
 * cannot be downgraded). We only need the symbol that libSystem exports on
 * jailbroken devices, so reference it through an assembler label instead of the
 * SDK declaration. */
extern kern_return_t UTM_IOServiceAuthorize(io_service_t service, uint32_t options) __asm__("_IOServiceAuthorize");

extern int proc_pidinfo(int pid, int flavor, uint64_t arg, void *buffer, int buffersize);

extern kern_return_t _IOServiceSetAuthorizationID(io_service_t service, uint64_t authorizationID);

/* bsd/sys/proc_info.h */
struct proc_uniqidentifierinfo {
    uint8_t                 p_uuid[16];        /* UUID of the main executable */
    uint64_t                p_uniqueid;        /* 64 bit unique identifier for process */
    uint64_t                p_puniqueid;        /* unique identifier for process's parent */
    uint64_t                p_reserve2;        /* reserved for future use */
    uint64_t                p_reserve3;        /* reserved for future use */
    uint64_t                p_reserve4;        /* reserved for future use */
};

#define PROC_PIDUNIQIDENTIFIERINFO    17

/**
 * On iOS, IOServiceAuthorizeAgent (XPC) is not defined, so we hook the call and set the authorization ID directly.
 * This requires the `com.apple.private.iokit.IOServiceSetAuthorizationID` entitlement.
 */
static kern_return_t IOServiceAuthorizeReplacement(io_service_t service, uint32_t options) {
    kern_return_t status;
    pid_t processID;
    struct proc_uniqidentifierinfo authorizationID = { 0 };
    
    processID = getpid();
    proc_pidinfo(processID, PROC_PIDUNIQIDENTIFIERINFO, 0, &authorizationID, sizeof(authorizationID));
    
    status = _IOServiceSetAuthorizationID(service, authorizationID.p_uniqueid);
    
    return status;
}

__attribute__ ((used, section ("__DATA,__interpose")))
static struct {
    void *replacement, *original;
} replace_IOServiceAuthorize = { IOServiceAuthorizeReplacement, UTM_IOServiceAuthorize };
#endif
