#ifndef VRC_LOADERS_CPARSER_H
#define VRC_LOADERS_CPARSER_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct Graph Graph;

void build_graph(const char *filename, const char *const *args, int num_args,
                 Graph *g, bool verbose, char **diagnostic);

#ifdef __cplusplus
}
#endif

#endif
