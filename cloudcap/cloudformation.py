import cfn_flip
import logging
import networkx as nx
import cloudcap.utils as utils

logger = logging.getLogger(__name__)


class CloudFormationTemplateError(Exception):
    pass


class CloudFormationStack:
    """A CloudFormation Stack, usually instantiated from a CloudFormation template file."""

    def __init__(self, template, path=""):
        self.path = path
        self.template = template
        self.resources = []
        self._init_dependency_graph()

    def _init_dependency_graph(self):
        self.dependency_graph = nx.DiGraph()
        resources = self.template["Resources"]
        for r in resources:
            self.dependency_graph.add_node(r)

        for r1 in resources:
            for r2, r2_body in resources.items():
                if utils.value_exists_in_nested_structure(r2_body, r1):
                    self.dependency_graph.add_edge(r1, r2)

        self.dependency_order = list(nx.topological_sort(self.dependency_graph))

        logger.debug(
            f"CloudFormation template ({self.path}) dependency graph: {self.dependency_graph.edges}"
        )

        logger.debug(
            f"CloudFormation template ({self.path}) dependency order: {self.dependency_order}"
        )

    @classmethod
    def from_file(cls, fpath: str):
        with open(fpath, "r") as f:
            try:
                data = cfn_flip.load_yaml(f)
                logger.info(f"Loaded {fpath} as CloudFormation template in YAML format")
            except:
                try:
                    data = cfn_flip.load_json(f)
                    logger.info(
                        f"Loaded {fpath} as a CloudFormation template in JSON format"
                    )
                except:
                    raise CloudFormationTemplateError(
                        f"Unable to load {fpath} as a CloudFormation template"
                    )

        return cls(data, path=fpath)
