import numpy as np
import neuronav.utils as utils
from neuronav.agents.base_agent import BaseAgent
from neuronav.agents.td_agents import TDSR


class MBV(BaseAgent):
    """
    Implementation of Model-Based Value Iteration Algorithm
    """

    def __init__(
        self,
        state_size: int,
        action_size: int,
        lr: float = 1e-1,
        gamma: float = 0.99,
        poltype: str = "softmax",
        beta: float = 1e4,
        epsilon: float = 1e-1,
        weights: str = "direct",
        w_value: float = 1.0,
        max_iter: int = 1,
        tol : float = 0.01,
        **kwargs
    ):
        super().__init__(state_size, action_size, lr, gamma, poltype, beta, epsilon)
        self.weights = weights
        self.T = np.zeros([action_size, state_size, state_size])
        self.w = np.zeros(state_size)
        self.base_Q = np.zeros([self.action_size, self.state_size])
        self.w_value = w_value
        self.max_iter = max_iter
        self.tol = tol

    def q_estimate(self, state):
        Q = self.Q
        return Q[:, state]

    def sample_action(self, state):
        return self.base_sample_action(self.q_estimate(state))

    def update_w(self, current_exp):
        s, a, s_1, r, _ = current_exp
        if self.weights == "direct":
            error = r - self.w[s_1]
            self.w[s_1] += self.lr * error
            #if error > 0:
                #self.update_q()
        return np.linalg.norm(error)

    def update_t(self, current_exp, next_exp=None, prospective=False):
        s = current_exp[0]
        s_a = current_exp[1]
        s_1 = current_exp[2]
        next_onehot = utils.onehot(s_1, self.state_size)
        if not (self.T[s_a, s] == next_onehot).all():
            self.T[s_a, s] = next_onehot
            self.base_Q = np.zeros([self.action_size, self.state_size])
            #self.update_q()
        return None

    def update_q(self, max_iter=1):
        for num_iteration in range(max_iter):

            q = self.Q

            for s in range(self.state_size):
                for a in range(self.action_size):
                    if np.sum(self.T[a, s]) > 0:
                        s_1 = np.argmax(self.T[a, s])
                        q_1 = self.base_Q[:, s_1]
                        v_next = self.w_value * np.max(q_1) + (1 - self.w_value) * np.min(q_1)
                        self.base_Q[a, s] = self.w[s_1] + self.gamma * v_next

            delta = np.abs(self.Q - q)
            if np.all(delta < self.tol): 
                break

        
    def _update(self, current_exp, **kwargs):
        self.update_t(current_exp, **kwargs)
        w_error = self.update_w(current_exp)
        self.update_q(self.max_iter)
        td_error = {"w": np.linalg.norm(w_error)}
        return td_error

    def get_policy(self):
        Q = self.Q
        return self.base_get_policy(Q)

    @property
    def Q(self):
        return self.base_Q.copy()


class SRMB(BaseAgent):
    """
    A hybrid Success / Model-based algorithm.
    """

    def __init__(
        self,
        state_size: int,
        action_size: int,
        lr: float = 1e-1,
        gamma: float = 0.99,
        poltype: str = "softmax",
        beta: float = 1e4,
        epsilon: float = 1e-1,
        mix: float = 0.5,
        weights: str = "direct",
        max_iter: int = 1,
        tol: float = 0.01,
        w_value: float = 1.0,
        **kwargs
    ):
        super().__init__(state_size, action_size, lr, gamma, poltype, beta, epsilon)
        self.mix = mix
        self.max_iter = max_iter
        self.tol = tol
        self.w_value = w_value

        self.MB_agent = MBV(
            state_size, action_size, lr, gamma, poltype, beta, epsilon, weights, w_value, max_iter, tol
        )
        self.SR_agent = TDSR(
            state_size, action_size, lr, gamma, poltype, beta, epsilon, None, weights, w_value
        )

    @property
    def Q(self):
        return self.MB_agent.Q * self.mix + self.SR_agent.Q * (1 - self.mix)

    def update_w(self, current_exp):
        self.MB_agent.update_w(current_exp)
        self.SR_agent.update_w(current_exp)

    def _update(self, current_exp):
        self.MB_agent._update(current_exp)
        self.SR_agent._update(current_exp)

    def q_estimates(self, state):
        mb_q = self.MB_agent.q_estimate(state)
        sr_q = self.SR_agent.q_estimate(state)
        return mb_q * self.mix + sr_q * (1 - self.mix)

    def sample_action(self, state):
        return self.base_sample_action(self.q_estimates(state))




class MBV_R(BaseAgent):
    """
    Implementation of Model-Based Value Iteration Algorithm with the reward function given
    """

    def __init__(
        self,
        state_size: int,
        action_size: int,
        r_fun,                #numpy array with the reward function per state
        lr: float = 1e-1,
        gamma: float = 0.99,
        poltype: str = "softmax",
        beta: float = 1e4,
        epsilon: float = 1e-1,
        weights: str = "direct",
        w_value: float = 1.0,
        **kwargs
    ):
        super().__init__(state_size, action_size, lr, gamma, poltype, beta, epsilon)
        self.weights = weights
        self.T = np.zeros([action_size, state_size, state_size])
        self.w = r_fun
        self.base_Q = np.zeros([self.action_size, self.state_size])
        self.w_value = w_value

    def q_estimate(self, state):
        Q = self.Q
        return Q[:, state]

    def sample_action(self, state):
        return self.base_sample_action(self.q_estimate(state))

    def update_w(self, current_exp):
        s, a, s_1, r, _ = current_exp
        if self.weights == "direct":
            error = r - self.w[s_1]
            self.w[s_1] += self.lr * error
            if error > 0:
                self.update_q(10)
        return np.linalg.norm(error)

    def update_t(self, current_exp, next_exp=None, prospective=False):
        s = current_exp[0]
        s_a = current_exp[1]
        s_1 = current_exp[2]
        next_onehot = utils.onehot(s_1, self.state_size)
        if not (self.T[s_a, s] == next_onehot).all():
            self.T[s_a, s] = next_onehot
            self.base_Q = np.zeros([self.action_size, self.state_size])
            self.update_q(10)
        return None

    def update_q(self, iters=1):
        for _ in range(iters):
            for s in range(self.state_size):
                for a in range(self.action_size):
                    if np.sum(self.T[a, s]) > 0:
                        s_1 = np.argmax(self.T[a, s])
                        q_1 = self.base_Q[:, s_1]
                        v_next = self.w_value * np.max(q_1) + (1 - self.w_value) * np.min(q_1)
                        self.base_Q[a, s] = self.w[s_1] + self.gamma * v_next

    def _update(self, current_exp, **kwargs):
        self.update_t(current_exp, **kwargs)
        w_error = self.update_w(current_exp)
        self.update_q()
        td_error = {"w": np.linalg.norm(w_error)}
        return td_error

    def get_policy(self):
        Q = self.Q
        return self.base_get_policy(Q)

    @property
    def Q(self):
        return self.base_Q.copy()