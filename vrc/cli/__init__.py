from ..graph import Graph
import typing


def serialize_graph(graph: Graph, f: typing.TextIO) -> None:
    node_to_file = dict()
    for file in graph.all_files():
        for node in graph.all_nodes_for_file(file):
            node_to_file[node] = file

    for node in graph.all_nodes(True):
        if graph.is_node_external(node):
            print("node", "--external", node, file=f)
        else:
            print("node", node, node_to_file.get(node, ""), file=f)

    for label in sorted(graph.labels()):
        for node in graph.labeled_nodes(label):
            print("label", label, node, file=f)

    for node in graph.all_nodes(False):
        for target in graph.callees(node, True, True):
            print("edge", node, target, graph.edge_type(node, target), file=f)


def source(inf: typing.Iterator[str], exit_first: bool) -> None:
    from . import main
    main.SourceCommand.do_source(inf, exit_first)
