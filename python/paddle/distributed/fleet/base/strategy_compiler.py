#   Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


def maximum_path_len_algo(optimizer_list):
    max_idx = 0
    max_len = 0
    candidates = []
    for idx, opt in enumerate(optimizer_list):
        local_buffer = [opt]
        for opt_inner in optimizer_list:
            if opt._can_update(opt_inner):
                local_buffer.append(opt_inner)
        if len(local_buffer) > max_len:
            max_idx = idx
            max_len = len(local_buffer)
        candidates.append(local_buffer)
    if len(candidates) == 0:
        return None
    for idx, opt in enumerate(candidates[max_idx][:-1]):
        opt._update_inner_optimizer(candidates[max_idx][idx + 1])
    return candidates[max_idx]


class StrategyCompilerBase(object):
    def __init__(self):
        pass


class StrategyCompiler(StrategyCompilerBase):
    """
    StrategyCompiler is responsible for meta optimizers combination
    Generally, a user can define serveral distributed strategies that
    can generate serveral meta optimizer. The combination of these 
    meta optimizers should have the right order to apply the optimizers'
    minimize function.
    This class is responsible for the executable distributed optimizer
    generation.
    """

    def __init__(self):
        super(StrategyCompiler, self).__init__()
        self._meta_optimizer = None
        self._graph_optimizer = None
        self._valid_optimizer_list = None
        self._user_defined_strategy = None
        self._meta_optimizer_candidates = []
        self._graph_optimizer_candidates = []

    def _get_valid_strategy(self, dist_strategy, can_not_apply_optimizer_list):
        import copy
        valid_strategy = copy.copy(dist_strategy)
        invalid_optimizers = []
        for candidate in self._meta_optimizer_candidates:
            is_valid = False
            for valid in self._meta_optimizers:
                if candidate.__class__.__name__ == valid.__class__.__name__:
                    is_valid = True
                    break
            if not is_valid:
                invalid_optimizers.append(candidate)
        for opt in invalid_optimizers:
            opt._disable_strategy(valid_strategy)
        for opt in can_not_apply_optimizer_list:
            opt._disable_strategy(valid_strategy)
        return valid_strategy

    """
    Meta Optimizer Type A: rewrite forward, backward. e.g. recompute, async, sync, pipeline.
                           results will be splitted in async, sync, pipeline
    Meta Optimizer Type B: rewrite forward, 
                           e.g. AMP and the corresponding backward is generated by rewritten forward
    Meta Opitmizer Type B: rewrite backward. e.g. gradient fusion
    Meta Optimizer Type D: rewrite optimize. e.g. lars, lamb, localsgd, gradient merge, dgc
    Meta Optimizer Type E: only transpile to Graph structure for runtime,
                           currently, grad fusion and kernel fusion, sync batch-norm included.
                           we will remove grad fusion and sync batch-norm
    """

    def generate_optimizer(self, loss, role_maker, optimizer,
                           user_defined_strategy, meta_optimizer_list,
                           graph_optimizer_list):
        self._user_defined_strategy = user_defined_strategy
        self._meta_optimizer_candidates = meta_optimizer_list
        self._graph_optimizer_candidates = graph_optimizer_list

        if len(meta_optimizer_list) == 0 and len(graph_optimizer_list) == 0:
            return optimizer, None
        else:
            # currently, we use heuristic algorithm to select
            # meta optimizers combinations
            meta_optimizers = maximum_path_len_algo(meta_optimizer_list)
            graph_optimizers = maximum_path_len_algo(graph_optimizer_list)
            # should design a distributed strategy update interface
            # when we have finally decided the combination of meta_optimizer
            # and graph_optimizer, the corresponding distributed strategy
            # should be updated.

            self._meta_optimizers = meta_optimizers
            self._graph_optimizers = graph_optimizers

            return_meta = None if meta_optimizers == None else meta_optimizers[
                0]
            return_graph = None if graph_optimizers == None else graph_optimizers[
                0]
            return return_meta, return_graph
