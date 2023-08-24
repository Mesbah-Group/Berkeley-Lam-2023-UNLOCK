# model predictive controller
#
# This script provides definitions of classes that can be used for model
# predictive control (MPC) schemes. This script is part of the package of code
# that produces the results of the following paper:
#
#
# Requirements:
# * Python 3
# * CasADi [https://web.casadi.org]
#
# Copyright (c) 2021 Mesbah Lab. All Rights Reserved.
# Contributor(s): Kimberly Chan
#
# This file is under the MIT License. A copy of this license is included in the
# download of the entire code package (within the root folder of the package).

import sys
sys.dont_write_bytecode = True
import os
import casadi as cas
import numpy as np
import itertools


class MPC():
    """
    MPC is a super class designed to be a template for particular
    implementations of model predictive controllers (MPCs). Users should develop
    their own MPCs by using the general structure/methods provided below. Upon
    initialization of this class or any of its child classes, users should
    provide a Python dict that contains all of the relevant problem information.
    This class is designed to be used with CasADi to generate the optimization
    problems associated with MPC. Users are referred to the CasADi documentation
    for more information on CasADi.
    """

    def __init__(self, prob_info):
        super(MPC, self).__init__()
        self.prob_info = prob_info
        self.mpc_type = None

    def get_mpc(self, arg):
        """
        This method should generate the MPC problem by unpacking relevant
        information from the prob_info dict defined upon instantiation of the
        class. Upon defining the optimization problem, this method should save
        and/or return the appropriate objects such that this object may be
        called upon later. (e.g. if using the Opti stack interface of CasADi,
        save/return the objects that reference the optimization object
        (typically named opti) and the optimization variable references)
        """
        pass

    def reset_initial_guesses(self, arg):
        """
        This method should reset any initial guesses of the decision variables
        passed into the optimization problem. This method provides a way to
        simulate repeated solves of the optimization problem without re-defining
        an entirely new problem. If using the Opti stack interface of CasADi,
        this method mainly involves using the set_initial() method of the Opti
        object.
        """
        pass

    def set_parameters(self, arg):
        """
        This method should (re)set any parameters in the optimization problem.
        This method provides a way to simulated consistent and repeated solves
        of the optimization problem without re-defining an entirely new problem.
        If using the Opti stack interface of CasADi, this method mainly involves
        using the set_value() method of the Opti object.
        """
        pass

    def solve_mpc(self, arg):
        """
        This method should solve the optimization problem and return/save the
        relavent optimal variables. For MPC, this is typically the first optimal
        input determined by the solver. Users may also wish to return other
        values of the optimization problem and/or the entire solution of the
        optimization problem. This method should also handle any Exceptions that
        may occur upon a call to solve the optimization problem in the form of a
        try/except clause. If using the Opti stack interface of CasADi, this
        method mainly involves the call to the solve() method of the Opti
        object, as well as calls to the value() method of OptiSolution/Opti
        objects.
        """
        pass

class EconomicMPC(MPC):
    """
    This class defines an economic MPC implementation. This class utilizes the
    Opti stack interface of CasADi.
    """

    def __init__(self, prob_info):
        super(EconomicMPC, self).__init__(prob_info)
        self.mpc_type = 'economic'

    def get_mpc(self):
        """
        This method creates the optimization problem for the MPC. All
        information necessary for the creation of this controller is passed upon
        instantiation of this object within the prob_info dict. For more details
        on the optimization problem, the user is referred to the paper
        associated with the release of this code.

        This code uses IPOPT for the NLP solver which is distributed with
        CasADi. Users are referred to IPOPT [https://coin-or.github.io/Ipopt/]
        and the associated paper for more information on this solver.
        """
        # unpack relavant problem information
        Np = self.prob_info['Np']
        # x0 = self.prob_info['x0']

        nu = self.prob_info['nu']
        nx = self.prob_info['nx']
        ny = self.prob_info['ny']
        nyc = self.prob_info['nyc']
        nw = self.prob_info['nw']

        u_min = self.prob_info['u_min']
        u_max = self.prob_info['u_max']
        x_min = self.prob_info['x_min']
        x_max = self.prob_info['x_max']
        y_min = self.prob_info['y_min']
        y_max = self.prob_info['y_max']

        u_init = self.prob_info['u_init']
        x_init = self.prob_info['x_init']
        y_init = self.prob_info['y_init']

        f = self.prob_info['f']
        h = self.prob_info['h']
        lstage = self.prob_info['lstage']
        lstage2 = self.prob_info['lstage2']

        reduce_dinput = False
        constrain_dinput = False
        if 'ustage' in self.prob_info.keys():
            ustage = self.prob_info['ustage']
            reduce_dinput = True
        if 'du_max' in self.prob_info.keys():
            du_max = self.prob_info['du_max']
            du_min = self.prob_info['du_min']
            constrain_dinput = True

        # create NLP opti object
        opti = cas.Opti()

        # Initialize container lists for all states, inputs, outputs, and
        # predicted noise over horizon
        X = [0 for j in range(Np+1)]
        Y = [0 for j in range(Np+1)]
        U = [0 for j in range(Np)]
        wPred = [0 for j in range(Np)]

        J = 0 # initialize cost/objective function
        href_t = 40

        href = opti.parameter(nyc) # target/reference output
        opti.set_value(href, np.zeros((nyc,1)))

        h0 = opti.parameter(nyc) # initial thickness
        opti.set_value(h0, np.zeros((nyc,1)))

        # define parameter(s), variable(s), and problem
        X[0] = opti.parameter(nx) # initial state as a parameter
        opti.set_value(X[0], np.zeros((nx,1)))

        Y[0] = opti.variable(ny) # initial output variable
        opti.subject_to(Y[0] == h(X[0]))
        opti.set_initial(Y[0], y_init)

        # the loop below systematically defines the variables of the optimal
        # control problem (OCP) over the prediction horizon
        for k in range(Np):
            # variable and constraints for u_{k}
            U[k] = opti.variable(nu)
            opti.subject_to(opti.bounded(u_min, U[k], u_max))
            opti.set_initial(U[k], u_init)

            #
            #
            Jstage = (lstage(X[k], np.zeros((nw,1)))-href)**2 + (lstage2(X[k], np.zeros((nw,1)))-href_t)**2
            #Jstage = (lstage2(X[k], np.zeros((nw,1)))-href_i2)**2
            J += Jstage # add to the cost (construction of the objective)

            # variable x_{k+1}
            X[k+1] = opti.variable(nx)
            opti.subject_to(opti.bounded(x_min, X[k+1], x_max))
            opti.set_initial(X[k+1], x_init)

            # variable y_{k+1}
            Y[k+1] = opti.variable(ny)
            opti.subject_to(opti.bounded(y_min, Y[k+1], y_max))
            opti.set_initial(Y[k+1], y_init)

            # dynamics constraint
            opti.subject_to(X[k+1] == f(X[k],U[k],wPred[k]))

            # output equality constraint
            opti.subject_to(Y[k+1] == h(X[k+1]))

            if k>0 and reduce_dinput:
                J += ustage(U[k],U[k-1])
            elif k>0 and constrain_dinput:
                opti.subject_to(opti.bounded(du_min, U[k]-U[k-1], du_max))

        # terminal cost and constraints
        J_end = (lstage(X[-1], np.zeros((nw,1)))-href)**2 + (lstage2(X[-1], np.zeros((nw,1)))-href_t)**2
        #J_end = (lstage2(X[-1], np.zeros((nw,1)))-href_i2)**2
        J += J_end

        #Jcon = J 
        #J = (Jcon-href)**2

        # set to minimize objective/cost
        opti.minimize( J )

        # set solver options
        p_opts = {'verbose': 0,
                  'expand': True,
                  'print_time': 0}          # problem options
        s_opts = {'max_iter': 1000,
                  'print_level': 0,
                  'tol': 1e-6}# solver options
        #'constr_viol_tol':0.001
        opti.solver('ipopt', p_opts, s_opts) # add the solver to the opti object

        # save list containers of variables/parameters into a dict for portability
        opti_vars = {}
        opti_vars['U'] = U
        opti_vars['X'] = X[1:]
        opti_vars['Y'] = Y
        opti_vars['J'] = J

        opti_params  = {}
        opti_params['X0'] = X[0]
        opti_params['href'] = href
        opti_params['h0'] = h0

        # save opti object and variable containers as attributes of NominalMPC
        # object
        self.opti = opti
        self.opti_vars = opti_vars
        self.opti_params = opti_params

        return opti, opti_vars, opti_params

    def solve_mpc(self, warm_start=True):
        """
        This method solves the MPC as defined by the get_mpc() method of this
        class. This method can only be called after the the get_mpc() method has
        been called (i.e., the optimization problme must be defined before it
        can be solved).
        """
        # extract all keys from the opti variables dict
        opti_var_keys = [*self.opti_vars]
        opti_param_keys = [*self.opti_params]

        # unpack relevant information from problem creation
        u_min = self.prob_info['u_min']
        u_max = self.prob_info['u_max']

        feas = True
        res = {}
        try:
            sol = self.opti.solve()

            for key in opti_var_keys:
                if key == 'J':
                    res[key] = sol.value(self.opti_vars[key])
                else:
                    var = self.opti_vars[key]
                    r = len(var) # Np
                    nx = (var[0]).size1()
                    values = np.zeros((nx,r))
                    for j in range(r):
                        values[:,j,] = sol.value(var[j])

                    res[key] = values

            res['Ufull'] = res['U']
            res['U'] = res['U'][:,0]

            for key in opti_param_keys:
                if key in ['href', 'h0', 'X0']:
                    res[key] = sol.value(self.opti_params[key])
                else:
                    var = self.opti_params[key]
                    r = len(var) # Np
                    nx = (var[0]).size1()
                    values = np.zeros((nx,r))
                    for j in range(r):
                        values[:,j] = sol.value(var[j])

                    res[key] = values

            if warm_start:
                self.opti.set_initial(sol.value_variables())

        except Exception as e:
            print(e)
            # if solve fails, get the last value
            feas = False

            for key in opti_var_keys:
                if key == 'J':
                    res[key] = self.opti.debug.value(self.opti_vars[key])
                else:
                    var = self.opti_vars[key]
                    r = len(var) # Np
                    nx = (var[0]).size1()
                    values = np.zeros((nx,r))
                    for j in range(r):
                        values[:,j] = self.opti.debug.value(var[j])

                    res[key] = values

            res['Ufull'] = res['U']
            res['U'] = res['U'][:,0]

            for key in opti_param_keys:
                if key in ['href', 'h0', 'X0']:
                    res[key] = self.opti.debug.value(self.opti_params[key])
                else:
                    var = self.opti_params[key]
                    r = len(var) # Np
                    nx = (var[0]).size1()
                    values = np.zeros((nx,r))
                    for j in range(r):
                        values[:,j] = self.opti.debug.value(var[j])

                    res[key] = values

            u = res['U']
            res['U'] = np.maximum(np.minimum(u, u_max), u_min)
            # print('U_0:', res['U'])
            # print('J:', res['J'])

        return res, feas

    def reset_initial_guesses(self):
        """
        This method resets the intial guesses for the variables of the
        optimization problem back to those defined in the problem_info dict
        provided upon instantiation of the OffsetFreeMPC object.
        """
        # unpack relevant information from the prob_info dict
        Np = self.prob_info['Np']
        u_init = self.prob_info['u_init']
        x_init = self.prob_info['x_init']
        y_init = self.prob_info['y_init']

        # unpack relevant variable containers from problem creation
        U = self.opti_vars['U']
        X = self.opti_vars['X']
        Y = self.opti_vars['Y']

        self.opti.set_initial(Y[0], y_init)
        for k in range(Np):
            self.opti.set_initial(U[k], u_init)
            self.opti.set_initial(X[k], x_init)
            self.opti.set_initial(Y[k+1], y_init)

    def set_parameters(self, params_list):
        """
        This method sets the values of the parameters of the optimization
        problem to those provided as arguments to this method. The argument
        params_list is a list of new parameter values to set in the same order
        as the opti_param keys.
        """

        # unpack parameter containers
        X0 = self.opti_params['X0']
        href = self.opti_params['href']
        h0 = self.opti_params['h0']

        # unpack params_list argument
        x0 = params_list[0]
        hRef = params_list[1]
        hp0 = params_list[2]

        # reset initial and target CEM
        self.opti.set_value(h0, hp0)
        self.opti.set_value(href, hRef)

        # reset initial condition
        self.opti.set_value(X0, x0)


class MultiStageMPC(MPC):
    """
    This class defines a multistage MPC implementation. This class utilizes the
    Opti stack interface of CasADi.
    """

    def __init__(self, prob_info):
        super(MultiStageMPC, self).__init__(prob_info)
        self.mpc_type = 'multistage'

    def get_mpc(self):
        """
        This method creates the optimization problem for the MPC. All
        information necessary for the creation of this controller is passed upon
        instantiation of this object within the prob_info dict. For more details
        on the optimization problem, the user is referred to the paper
        associated with the release of this code.

        This code uses IPOPT for the NLP solver which is distributed with
        CasADi. Users are referred to IPOPT [https://coin-or.github.io/Ipopt/]
        and the associated paper for more information on this solver.
        """
        # unpack relavant problem information
        Np = self.prob_info['Np']
        N_robust = self.prob_info['N_robust']
        case_idx = self.prob_info['case_idx']
        Wset = self.prob_info['Wset']
        # x0 = self.prob_info['x0']

        nu = self.prob_info['nu']
        nx = self.prob_info['nx']
        ny = self.prob_info['ny']
        nyc = self.prob_info['nyc']
        nw = self.prob_info['nw']

        u_min = self.prob_info['u_min']
        u_max = self.prob_info['u_max']
        x_min = self.prob_info['x_min']
        x_max = self.prob_info['x_max']
        y_min = self.prob_info['y_min']
        y_max = self.prob_info['y_max']

        u_init = self.prob_info['u_init']
        x_init = self.prob_info['x_init']
        y_init = self.prob_info['y_init']

        f = self.prob_info['f']
        h = self.prob_info['h']
        r = self.prob_info['r']
        lstage = self.prob_info['lstage']
        reduce_dinput = False
        constrain_dinput = False
        if 'ustage' in self.prob_info.keys():
            ustage = self.prob_info['ustage']
            reduce_dinput = True
        if 'du_max' in self.prob_info.keys():
            du_max = self.prob_info['du_max']
            du_min = self.prob_info['du_min']
            constrain_dinput = True

        # Build the scenario matrix with all the combinations. Dimension (Ncases^Nrobust, Nrobust)
        scenario_mat = np.array(list(itertools.product(case_idx, case_idx)))
        N_scenarios = scenario_mat.shape[0]

        # Weights for cost function
        w_i = (1/N_scenarios)*np.ones((N_scenarios,1))

        # create NLP opti object
        opti = cas.Opti()

        # Initialize container lists for all states, inputs, outputs, and
        # predicted noise over horizon (Np by Nscenarios)
        X = [[0 for i in range(N_scenarios)] for j in range(Np+1)]
        Y = [[0 for i in range(N_scenarios)] for j in range(Np+1)]
        U = [[0 for i in range(N_scenarios)] for j in range(Np)]
        wPred = [[0 for i in range(N_scenarios)] for j in range(Np)]

        J = 0 # initialize cost/objective function
        n_disc = 0

        CEMref = opti.parameter(nyc) # target/reference output
        opti.set_value(CEMref, np.zeros((nyc,1)))

        CEM0 = opti.parameter(nyc) # initial CEM
        opti.set_value(CEM0, np.zeros((nyc,1)))

        for n_sc in range(N_scenarios):
            sc_vec = scenario_mat[n_sc,:].T
            w_idx = sc_vec - np.amin(scenario_mat)

            # define parameter(s), variable(s), and problem
            X[0][n_sc] = opti.parameter(nx) # initial state as a parameter
            opti.set_value(X[0][n_sc], np.zeros((nx,1)))

            Y[0][n_sc] = opti.variable(ny) # initial output variable
            opti.subject_to(Y[0][n_sc] == h(X[0][n_sc]))
            opti.set_initial(Y[0][n_sc], y_init)
            n_disc += ny

            # the loop below systematically defines the variables of the optimal
            # control problem (OCP) over the prediction horizon
            for k in range(Np):
                # variable and constraints for u_{k}
                U[k][n_sc] = opti.variable(nu)
                opti.subject_to(opti.bounded(u_min, U[k][n_sc], u_max))
                opti.set_initial(U[k][n_sc], u_init)
                n_disc += nu

                # noise prediction parameter
                wPred[k][n_sc] = opti.parameter(nw) # predicted noise
                # Change bounds depending on robust horizon
                if k < N_robust:
                    opti.set_value(wPred[k][n_sc], Wset[:,w_idx[k]])
                # elif k < Np:
                #     opti.set_value(wPred[k][n_sc], Wset[:,w_idx[N_robust-1]])
                else:
                    opti.set_value(wPred[k][n_sc], np.zeros((nw,1)))

                Jstage = lstage(X[k][n_sc], wPred[k][n_sc])
                J += w_i[n_sc]*Jstage # add to the cost (construction of the objective)

                # variable x_{k+1}
                X[k+1][n_sc] = opti.variable(nx)
                opti.subject_to(opti.bounded(x_min, X[k+1][n_sc], x_max))
                opti.set_initial(X[k+1][n_sc], x_init)
                n_disc += nx

                # variable y_{k+1}
                Y[k+1][n_sc] = opti.variable(ny)
                opti.subject_to(opti.bounded(y_min, Y[k+1][n_sc], y_max))
                opti.set_initial(Y[k+1][n_sc], y_init)
                n_disc += ny

                # dynamics constraint
                opti.subject_to(X[k+1][n_sc] == f(X[k][n_sc],U[k][n_sc],wPred[k][n_sc]))

                # output equality constraint
                opti.subject_to(Y[k+1][n_sc] == h(X[k+1][n_sc]))

                if k>0 and reduce_dinput:
                    J += ustage(U[k][n_sc],U[k-1][n_sc])
                elif k>0 and constrain_dinput:
                    opti.subject_to(opti.bounded(du_min, U[k][n_sc]-U[k-1][n_sc], du_max))

            # terminal cost and constraints
            J_end = lstage(X[-1][n_sc], np.zeros((nw,1)))
            J += w_i[n_sc]*J_end

        Jcon = J + CEM0
        J = (Jcon-CEMref)**2

        # Non-anticipativity constraint (first split)
        for jj in range(N_scenarios-1):
            opti.subject_to(U[0][jj] == U[0][jj+1])

        # Non-anticipativity constraint (second split)
        if N_robust > 1:
            n_usc = len(case_idx) # number of unique scenarios at each node
            scenario_vec = np.arange(N_scenarios)
            for ii in range(n_usc):
                # get the scenarios that correspond to the same parent node
                same_nodes = scenario_vec[scenario_mat[:,0] == case_idx[ii]]

                # add constraint
                for jj in range(len(same_nodes)-1):
                    opti.subject_to(U[1][same_nodes[jj]] == U[1][same_nodes[jj+1]])

        # set to minimize objective/cost
        opti.minimize( J )

        # set solver options
        discrete_vals = [False]*n_disc
        p_opts = {'verbose': 0,
                  'expand': True,
                  'discrete': tuple(discrete_vals),
                  'print_time': 0}          # problem options
        s_opts = {'max_iter': 1000,
                  'print_level': 0,
                  'tol': 1e-6}              # solver options
        opti.solver('ipopt', p_opts, s_opts) # add the solver to the opti object

        # save list containers of variables/parameters into a dict for portability
        opti_vars = {}
        opti_vars['U'] = U
        opti_vars['X'] = X[1:]
        opti_vars['Y'] = Y
        opti_vars['J'] = J

        opti_params  = {}
        opti_params['X0'] = X[0]
        opti_params['CEMref'] = CEMref
        opti_params['CEM0'] = CEM0
        opti_params['wPred'] = wPred

        # save opti object and variable containers as attributes of NominalMPC
        # object
        self.opti = opti
        self.opti_vars = opti_vars
        self.opti_params = opti_params

        return opti, opti_vars, opti_params

    def solve_mpc(self, warm_start=True):
        """
        This method solves the MPC as defined by the get_mpc() method of this
        class. This method can only be called after the the get_mpc() method has
        been called (i.e., the optimization problme must be defined before it
        can be solved).
        """
        # extract all keys from the opti variables dict
        opti_var_keys = [*self.opti_vars]
        opti_param_keys = [*self.opti_params]

        # unpack relevant information from problem creation
        u_min = self.prob_info['u_min']
        u_max = self.prob_info['u_max']

        feas = True
        res = {}
        try:
            sol = self.opti.solve()

            for key in opti_var_keys:
                if key == 'J':
                    res[key] = sol.value(self.opti_vars[key])
                else:
                    var = self.opti_vars[key]
                    r = len(var) # Np
                    c = len(var[0]) # Nscenarios
                    nx = (var[0][0]).size1()
                    values = np.zeros((nx,r,c))
                    for j in range(r):
                        for k in range(c):
                            values[:,j,k] = sol.value(var[j][k])

                    res[key] = values

            res['Ufull'] = res['U']
            res['U'] = res['U'][:,0,0]

            for key in opti_param_keys:
                if key == 'CEM0' or key == 'CEMref':
                    res[key] = sol.value(self.opti_params[key])
                elif key == 'X0':
                    var = self.opti_params[key]
                    c = len(var) # Nscenarios
                    nx = (var[0]).size1()
                    values = np.zeros((nx,c))
                    for k in range(c):
                        values[:,k] = sol.value(var[k])
                else:
                    var = self.opti_params[key]
                    r = len(var) # Np
                    c = len(var[0]) # Nscenarios
                    nx = (var[0][0]).size1()
                    values = np.zeros((nx,r,c))
                    for j in range(r):
                        for k in range(c):
                            values[:,j,k] = sol.value(var[j][k])

                    res[key] = values

            if warm_start:
                self.opti.set_initial(sol.value_variables())

        except Exception as e:
            print(e)
            # if solve fails, get the last value
            feas = False

            for key in opti_var_keys:
                if key == 'J':
                    res[key] = self.opti.debug.value(self.opti_vars[key])
                else:
                    var = self.opti_vars[key]
                    r = len(var) # Np
                    c = len(var[0]) # Nscenarios
                    nx = (var[0][0]).size1()
                    values = np.zeros((nx,r,c))
                    for j in range(r):
                        for k in range(c):
                            values[:,j,k] = self.opti.debug.value(var[j][k])

                    res[key] = values

            res['Ufull'] = res['U']
            res['U'] = res['U'][:,0,0]

            for key in opti_param_keys:
                if key == 'CEM0' or key == 'CEMref':
                    res[key] = self.opti.debug.value(self.opti_params[key])
                elif key == 'X0':
                    var = self.opti_params[key]
                    c = len(var) # Nscenarios
                    nx = (var[0]).size1()
                    values = np.zeros((nx,c))
                    for k in range(c):
                        values[:,k] = self.opti.debug.value(var[k])
                else:
                    var = self.opti_params[key]
                    r = len(var) # Np
                    c = len(var[0]) # Nscenarios
                    nx = (var[0][0]).size1()
                    values = np.zeros((nx,r,c))
                    for j in range(r):
                        for k in range(c):
                            values[:,j,k] = self.opti.debug.value(var[j][k])

                    res[key] = values

            u = res['U']
            res['U'] = np.maximum(np.minimum(u, u_max), u_min)
            # print('U_0:', res['U'])
            # print('J:', res['J'])

        return res, feas

    def reset_initial_guesses(self):
        """
        This method resets the intial guesses for the variables of the
        optimization problem back to those defined in the problem_info dict
        provided upon instantiation of the OffsetFreeMPC object.
        """
        # unpack relevant information from the prob_info dict
        Np = self.prob_info['Np']
        N_robust = self.prob_info['N_robust']
        case_idx = self.prob_info['case_idx']
        u_init = self.prob_info['u_init']
        x_init = self.prob_info['x_init']
        y_init = self.prob_info['y_init']

        # unpack relevant variable containers from problem creation
        U = self.opti_vars['U']
        X = self.opti_vars['X']
        Y = self.opti_vars['Y']

        N_scenarios = int(len(case_idx)**N_robust)

        for n_sc in range(N_scenarios):
            self.opti.set_initial(Y[0][n_sc], y_init)
            for k in range(Np):
                self.opti.set_initial(U[k][n_sc], u_init)
                self.opti.set_initial(X[k][n_sc], x_init)
                self.opti.set_initial(Y[k+1][n_sc], y_init)

    def set_parameters(self, params_list):
        """
        This method sets the values of the parameters of the optimization
        problem to those provided as arguments to this method. The argument
        params_list is a list of new parameter values to set in the same order
        as the opti_param keys.
        """
        Np = self.prob_info['Np']
        N_robust = self.prob_info['N_robust']
        case_idx = self.prob_info['case_idx']
        # Build the scenario matrix with all the combinations. Dimension (Ncases^Nrobust, Nrobust)
        scenario_mat = np.array(list(itertools.product(case_idx, case_idx)))
        N_scenarios = scenario_mat.shape[0]

        # unpack parameter containers
        X0 = self.opti_params['X0']
        CEMref = self.opti_params['CEMref']
        CEM0 = self.opti_params['CEM0']
        wPred = self.opti_params['wPred']

        # unpack params_list argument
        x0 = params_list[0]
        cemRef = params_list[1]
        cem0 = params_list[2]
        Wset = params_list[3]

        # reset initial and target CEM
        self.opti.set_value(CEM0, cem0)
        self.opti.set_value(CEMref, cemRef)

        # update initial state and uncertainty bounds
        for n_sc in range(N_scenarios):
            # reset initial condition
            self.opti.set_value(X0[n_sc], x0)

            sc_vec = scenario_mat[n_sc,:].T
            w_idx = sc_vec-np.amin(scenario_mat)

            for k in range(Np):
                # Change bounds depending on robust horizon
                if k < N_robust:
                    self.opti.set_value(wPred[k][n_sc], Wset[:,w_idx[k]])
                elif k < Np:
                    self.opti.set_value(wPred[k][n_sc], Wset[:,w_idx[N_robust-1]])
                else:
                    self.opti.set_value(wPred[k][n_sc], np.zeros((nw,1)))
