#pragma once
#include <cstddef>
#include <cstdint>

// C boundary keeps torch/CANN out of the executable's initial loader namespace.
// The Python bootstrap imports the extension normally before this API is queried.
struct QttsEventView {
    int64_t id, frames;
    int done;
    const char* pcm;
    size_t pcm_bytes;
    const char* reason;
};
using QttsEmit = void (*)(const QttsEventView*, void*);
struct QttsRuntimeAPI {
    uint32_t version;
    int64_t (*size)(void*);
    bool (*ready)(void*);
    int (*step)(void*, QttsEmit, void*);
    const char* (*last_error)();
};
extern "C" const QttsRuntimeAPI* qtts_runtime_api();
