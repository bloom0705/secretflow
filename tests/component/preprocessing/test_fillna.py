import logging
import os

import numpy as np
import pandas as pd
import pytest

from secretflow.component.data_utils import DistDataType
from secretflow.component.preprocessing.fillna import fillna, SUPPORTED_FILL_NA_METHOD
from secretflow.spec.v1.component_pb2 import Attribute
from secretflow.spec.v1.data_pb2 import DistData, TableSchema, VerticalTable
from secretflow.spec.v1.evaluation_pb2 import NodeEvalParam

from tests.conftest import TEST_STORAGE_ROOT


@pytest.mark.parametrize("strategy", SUPPORTED_FILL_NA_METHOD)
def test_fillna(comp_prod_sf_cluster_config, strategy):
    alice_input_path = "test_fillna/alice.csv"
    bob_input_path = "test_fillna/bob.csv"
    rule_path = "test_fillna/fillna.rule"
    sub_path = "test_fillna/substitution.csv"

    storage_config, sf_cluster_config = comp_prod_sf_cluster_config
    self_party = sf_cluster_config.private_config.self_party
    local_fs_wd = storage_config.local_fs.wd

    if self_party == "alice":
        df_alice = pd.DataFrame(
            {
                "id1": [str(i) for i in range(17)],
                "a1": ["K"] + ["F"] * 14 + ["M", "N"],
                "a2": [0.1, np.nan, 0.3] * 5 + [0.4] * 2,
                "a3": [1] * 17,
                "y": [0] * 17,
            }
        )

        os.makedirs(
            os.path.join(local_fs_wd, "test_fillna"),
            exist_ok=True,
        )

        df_alice.to_csv(
            os.path.join(local_fs_wd, alice_input_path),
            index=False,
        )
    elif self_party == "bob":
        df_bob = pd.DataFrame(
            {
                "id2": [str(i) for i in range(17)],
                "b4": [i for i in range(17)],
                "b5": [i for i in range(17)],
            }
        )

        os.makedirs(
            os.path.join(local_fs_wd, "test_fillna"),
            exist_ok=True,
        )

        df_bob.to_csv(
            os.path.join(local_fs_wd, bob_input_path),
            index=False,
        )

    param = NodeEvalParam(
        domain="preprocessing",
        name="fillna",
        version="0.0.1",
        attr_paths=[
            'strategy',
            'fill_value_float',
            'input/input_dataset/fill_na_features',
        ],
        attrs=[
            Attribute(s=strategy),
            Attribute(f=99.0),
            Attribute(ss=["a2", "b4", "b5"]),
        ],
        inputs=[
            DistData(
                name="input_data",
                type=str(DistDataType.VERTICAL_TABLE),
                data_refs=[
                    DistData.DataRef(uri=bob_input_path, party="bob", format="csv"),
                    DistData.DataRef(uri=alice_input_path, party="alice", format="csv"),
                ],
            )
        ],
        output_uris=[
            sub_path,
            rule_path,
        ],
    )

    meta = VerticalTable(
        schemas=[
            TableSchema(
                id_types=["str"],
                ids=["id2"],
                feature_types=["int32", "int32"],
                features=["b4", "b5"],
            ),
            TableSchema(
                id_types=["str"],
                ids=["id1"],
                feature_types=["str", "float32", "int32"],
                features=["a1", "a2", "a3"],
                label_types=["float32"],
                labels=["y"],
            ),
        ],
    )
    param.inputs[0].meta.Pack(meta)

    os.makedirs(
        os.path.join(local_fs_wd, "test_fillna"),
        exist_ok=True,
    )

    res = fillna.eval(
        param=param,
        storage_config=storage_config,
        cluster_config=sf_cluster_config,
    )

    assert len(res.outputs) == 2

    a_out = pd.read_csv(os.path.join(TEST_STORAGE_ROOT, "alice", sub_path))

    logging.warn(f"....... \n{a_out}\n.,......")

    b_out = pd.read_csv(os.path.join(TEST_STORAGE_ROOT, "bob", sub_path))

    logging.warn(f"....... \n{b_out}\n.,......")

    assert a_out.isnull().sum().sum() == 0, "DataFrame contains NaN values"
    assert b_out.isnull().sum().sum() == 0, "DataFrame contains NaN values"
