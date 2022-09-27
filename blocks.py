import numpy as np
import numba as nb

from GEModelTools import lag, lead, bound, bisection
from helper_functions import integrate_marg_util
from helper_functions import broyden_solver_cust
from helper_functions import obtain_J


@nb.njit
def NKPC_eq(x, par, r, s, Pi_plus):
    gap = s - (par.e_p - 1)/par.e_p

    kappa = (1-par.xi_p) * (1-par.xi_p/(1+r)) / par.xi_p \
            * par.e_p / (par.v_p + par.e_p - 1)

    NKPC = x - 1/(1+r) * kappa * gap - 1/(1+r)*Pi_plus

    return NKPC

@nb.njit
def NKPC_w_eq(x, par, s_w, Pi_w_plus):
    gap = s_w - (par.e_w - 1)/par.e_w

    kappa = (1-par.xi_w) * (1-par.xi_w*par.beta_mean) / par.xi_p \
            * par.e_w / (par.v_w + par.e_w - 1)

    NKPC_w = kappa * gap - par.beta_mean*Pi_w_plus

    return NKPC_w

# Question: scale inv adjustment costs?
@nb.njit
def adj_costs(K, K_plus, phi, delta_K):
    I = K_plus - (1 - delta_K) * K
    adj_costs = phi / 2 * (I / K - delta_K) ** 2 * K
    adj_costs_deriv1 = phi * (I / K  - delta_K)
    adj_costs_deriv2 = phi / K
    return adj_costs, adj_costs_deriv1, adj_costs_deriv2

@nb.njit
def inv_eq(Q, K_lag, K, K_plus, K_plus2, K_plus3, r_plus, delta_K, phi_K):
    S, S1, _ = adj_costs(K_plus, K_plus2, phi_K, delta_K)
    _, S1_plus, _ = adj_costs(K_plus2, K_plus3, phi_K, delta_K)
    I = K - (1 - delta_K) * K_lag
    I_plus = K_plus - (1 - delta_K) * K
    I_plus2 = K_plus2 - (1 - delta_K) * K_plus
    LHS = 1 + S + I_plus / I * S1
    RHS = Q + (1 / (1 + r_plus)) * (I_plus2 / I_plus) ** 2 * S1_plus
    return LHS - RHS

@nb.njit
def unpack_kwargs(d):
    """ simple unpacking funtion specific to the current residual function"""
    return d['par'], d['ss'], d['Y'], d['w'], d['r']

@nb.njit
def residual(x, kwargs_dict):
    """ residual function to optimize using the broyden solver

        :arg x: flattened np.array containing the unknowns"""

    # unpack
    par, ss, Y, w, r = unpack_kwargs(kwargs_dict)

    K, Q = flat_to_K_Q(x)  # back out the unknows from the flattened array
    # as K is fixed for t=0 and t=1 set these to ss value
    K = np.concatenate((np.array([ss.K, ss.K]), K))
    Q = np.concatenate((np.array([ss.Q, ss.Q]), Q))
    # init
    target1 = np.empty_like(Q)
    target2 = np.empty_like(K)

    # labor block
    N = (Y / (par.Theta * K ** par.alpha)) ** (1 / (1 - par.alpha))
    s = w * N / Y / (1 - par.alpha)
    rk = s * par.alpha * par.Theta * K ** (par.alpha - 1) * N ** (1 - par.alpha)

    # calculate values for target equation
    for t_ in range(par.T):
        t = (par.T - 1) - t_

        K_lag = K[t - 1] if t > 0 else ss.K
        K_plus = K[t + 1] if t < par.T - 1 else ss.K
        K_plus2 = K[t + 2] if t < par.T - 2 else ss.K
        K_plus3 = K[t + 3] if t < par.T - 3 else ss.K
        Q_plus = Q[t + 1] if t < par.T - 1 else ss.Q
        r_plus = r[t + 1] if t < par.T - 1 else ss.r
        rk_plus2 = rk[t + 2] if t < par.T - 2 else ss.rk
        N_plus2 = N[t + 2] if t < par.T - 2 else ss.N
        s_plus2 = s[t + 2] if t < par.T - 2 else ss.s
        rk_plus2 = rk[t + 2] if t < par.T - 2 else ss.rk

        # calculate targets
        Q_t = (1 / (1 + r_plus)) * (rk_plus2 + (1 - par.delta_K) * Q_plus)
        target1[t] = Q[t] - Q_t
        target2[t] = inv_eq(Q_t, K_lag, K[t], K_plus, K_plus2, K_plus3, r_plus, par.delta_K, par.phi_K)

    # return target1, target2
    return np.hstack((target1, target2)) # np.array((target1, target2)).reshape(-1)

@nb.njit
def flat_to_K_Q(x):
    """ Flat array into seperate arrays for K and Q"""
    nx = x.shape[0]
    assert nx%2 == 0.0
    nx_half = int(nx/2)
    return x[:nx_half], x[nx_half:]


@nb.njit
def block_pre(par, ini, ss, path, ncols=1):
    """ evaluate transition path - before household block """
    for ncol in nb.prange(ncols):
        r = path.r[ncol,:]
        ra = path.ra[ncol,:]
        rl = path.rl[ncol,:]
        i = path.i[ncol,:]
        Pi = path.Pi[ncol,:]
        Pi_w = path.Pi_w[ncol,:]
        G = path.G[ncol,:]
        tau = path.tau[ncol,:]
        B = path.B[ncol, :]
        Y = path.Y[ncol, :]
        N = path.N[ncol, :]
        I = path.I[ncol, :]
        K = path.K[ncol, :]
        Div = path.Div[ncol, :]
        Q = path.Q[ncol, :]
        C = path.C[ncol, :]
        L = path.L[ncol, :]
        A = path.A[ncol, :]
        C_hh = path.C_hh[ncol, :]
        L_hh = path.L_hh[ncol, :]
        A_hh = path.A_hh[ncol, :]
        # UCE_hh = path.UCE_hh[ncol, :]
        qB = path.qB[ncol, :]
        w = path.w[ncol, :]
        q = path.q[ncol, :]
        hh_wealth = path.hh_wealth[ncol, :]
        clearing_Y = path.clearing_Y[ncol, :]
        fisher_res = path.fisher_res[ncol, :]
        w_res = path.w_res[ncol, :]
        em = path.em[ncol, :]
        Z = path.Z[ncol, :]
        s = path.s[ncol, :]
        rk = path.rk[ncol, :]
        s_w = path.s_w[ncol, :]
        psi = path.psi[ncol, :]
        # nu = path.nu[ncol, :]
        # Theta = path.Theta[ncol, :]
        p_eq = path.p_eq[ncol, :]
        p_share = path.p_share[ncol, :]
        p_k = path.p_k[ncol, :]
        Div_k = path.Div_k[ncol, :]
        p_int = path.p_int[ncol, :]
        Div_int = path.Div_int[ncol, :]
        c = path.c
        a = path.a
        D = path.D

        #################
        # implied paths #
        #################

        # a. Production
            # inputs: r,w,Y
            # outputs: D,N,I,s

        # specify initial values for solver
        initQ = np.empty_like(Y)
        initK = np.empty_like(Y)
        initK[:] = ini.K
        initQ[:] = ini.Q
        # leave out fixed values for t = 0,1
        initK = initK[2:]
        initQ = initQ[2:]

        f_args = {'par': par,
                  'ss': ss,
                  'Y': Y,
                  'w': w,
                  'r': r}

        x0 = np.hstack((initK, initQ))
        # x0 = np.array([initK, initQ]).ravel()
        y0 = residual(x0, kwargs_dict=f_args)
        jac = obtain_J(residual, x0, y0, kwargs_dict=f_args)
        x_end = broyden_solver_cust(residual, x0, kwargs_dict=f_args, jac=jac,
                                    tol=1e-8, max_iter=200, backtrack_fac=0.5, max_backtrack=100,
                                    do_print=True)

        # x0 = np.array([initK, initQ]).ravel()
        # # compute jacobian to input
        # y0 = f(x0)
        # jac = obtain_J(f, x0, y0)
        #
        # # run solver
        # x_end = broyden_solver_cust(f, x0, jac=jac,
        #                     tol=1e-8, max_iter=200, backtrack_fac=0.5, max_backtrack=100,
        #                     do_print=False, do_print_unknowns=False, model=None,
        #                     fixed_jac=False)

        # back out K and Q
        K_opt, Q_opt = flat_to_K_Q(x_end)
        K[:]= np.concatenate((np.array([ss.K, ss.K]), K_opt))  # append fixed ss values for t=0,1
        Q[:] = np.concatenate((np.array([ss.Q, ss.Q]), Q_opt))

        # back out Investment
        for t in range(par.T):
            if t == 0:
                I[t] = ss.I
            elif t >= par.T - 1:
                I[t] = ss.K - (1 - par.delta_K) * K[t]
            else:
                I[t] = K[t + 1] - (1 - par.delta_K) * K[t]


        N[:] = (Y / (par.Theta * K ** par.alpha)) ** (1 / (1 - par.alpha))
        s[:] = w * N / Y / (1 - par.alpha)
        rk[:] = s * par.alpha * par.Theta * K ** (par.alpha - 1) * N ** (1 - par.alpha)


        # # For investment as if in the steady state
        # I[:] = par.delta_K * ss.K
        # for t in range(par.T):
        #     K_lag = K[t - 1] if t > 0 else ini.K
        #     I_lag = I[t - 1] if t > 0 else ini.I
        #     K[t] = (1 - par.delta_K) * K_lag + I_lag
        #
        # N[:] = (Y / (par.Theta * K ** par.alpha)) ** (1 / (1 - par.alpha))
        # s[:] = w * N / Y / (1-par.alpha)
        # rk[:] = s * par.alpha * par.Theta * K ** (par.alpha - 1) * N ** (1 - par.alpha)


        # Dividends
        for t_ in range(par.T):
            t = (par.T - 1) - t_
            K_plus = K[t + 1] if t < par.T - 1 else ss.K
            S, _, _ = adj_costs(K[t], K_plus, par.phi_K, par.delta_K)
            psi[t] = I[t] * S
            Div[t] = Y[t] - w[t] * N[t] - I[t] - psi[t]

        # b. solve NKPC
            # input: s
            # output: Pi
        for t_ in range(par.T):
            t = (par.T - 1) - t_
            Pi_plus = Pi[t + 1] if t < par.T - 1 else ss.Pi
            Pi[t] = bisection(NKPC_eq, -0.2, 0.2, args=(par, r[t], s[t], Pi_plus))

        # c. Taylor rule
        for t in range(par.T):
            i_lag = i[t - 1] if t > 0 else ini.i
            i[t] = (1 + r[t]) ** (1 - par.rho_m) * (1 + i_lag) ** (par.rho_m) \
                   * (1 + Pi[t]) ** ((1 - par.rho_m) * par.phi_pi) * (1 + em[t]) - 1

        # d. Finance
            # Inputs: Div, r
            # outputs: q, rl, ra
        rl[:] =  r - par.xi

        for t_ in range(par.T):
            t = (par.T - 1) - t_
            # q
            q_plus = q[t + 1] if t < par.T - 1 else ss.q
            q[t] = (1 + par.delta_q * q_plus) / (1 + r[t])

            # p
            p_eq_plus = p_eq[t + 1] if t < par.T - 1 else ss.p_eq
            Div_plus = Div[t + 1] if t < par.T - 1 else ss.Div
            p_eq[t] = (Div_plus + p_eq_plus) / (1 + r[t])

        for t_ in range(par.T):
            t = (par.T - 1) - t_
            Div_k[t] = rk[t] * K[t] - I[t] - psi[t]
            Div_int[t] = Div[t] - Div_k[t]

            Div_k_plus = Div_k[t + 1] if t < par.T - 1 else ss.Div_k
            p_k_plus = p_k[t + 1] if t < par.T - 1 else ss.p_k
            p_k[t] = (1 / (1 + r[t])) * (p_k_plus + Div_k_plus)

            Div_int_plus = Div_int[t + 1] if t < par.T - 1 else ss.Div_int
            p_int_plus = p_int[t + 1] if t < par.T - 1 else ss.p_int
            p_int[t] = (1 / (1 + r[t])) * (p_int_plus + Div_int_plus)


        for t in range(par.T):
            # ra
            p_eq_lag = p_eq[t - 1] if t > 0 else ini.p_eq
            q_lag = q[t - 1] if t > 0 else ini.q
            p_share[t] = p_eq_lag / (par.hh_wealth_Y_ratio - par.L_Y_ratio)
            ra[t] = p_share[t] * (Div[t] + p_eq[t]) / p_eq_lag \
                 + (1 - p_share[t]) * (1 + par.delta_q * q[t]) / q_lag - 1


        # TODO: Change to fiscal policy that depends on a shock
        # e. Fiscal
            # Inputs: q, w
            # Outputs: tau, Z, G
        G[:] = ss.G # constant government spending
        for t in range(par.T):
            B_lag = B[t-1] if t > 0 else ini.B
            tau[t] = par.psi * ss.q * (B_lag - ss.B) / ss.Y + ss.tau
            B[t] = (G[t] + (1 + par.delta_q * q[t]) * B_lag - tau[t] * w[t] * N[t]) / q[t]
            Z[:] = (1 - tau[t]) * w[t] * N[t]
            qB[t] = q[t] * B[t]

        hh_wealth[:] = p_eq + qB


@nb.njit
def block_post(par,ini,ss,path,ncols=1):
    """ evaluate transition path - after household block """

    for ncol in nb.prange(ncols):
        r = path.r[ncol,:]
        ra = path.ra[ncol,:]
        rl = path.rl[ncol,:]
        i = path.i[ncol,:]
        Pi = path.Pi[ncol,:]
        Pi_w = path.Pi_w[ncol,:]
        G = path.G[ncol,:]
        tau = path.tau[ncol,:]
        B = path.B[ncol, :]
        Y = path.Y[ncol, :]
        N = path.N[ncol, :]
        I = path.I[ncol, :]
        K = path.K[ncol, :]
        Div = path.Div[ncol, :]
        Q = path.Q[ncol, :]
        C = path.C[ncol, :]
        L = path.L[ncol, :]
        A = path.A[ncol, :]
        C_hh = path.C_hh[ncol, :]
        L_hh = path.L_hh[ncol, :]
        A_hh = path.A_hh[ncol, :]
        # UCE_hh = path.UCE_hh[ncol, :]
        qB = path.qB[ncol, :]
        w = path.w[ncol, :]
        q = path.q[ncol, :]
        hh_wealth = path.hh_wealth[ncol, :]
        clearing_Y = path.clearing_Y[ncol, :]
        fisher_res = path.fisher_res[ncol, :]
        w_res = path.w_res[ncol, :]
        em = path.em[ncol, :]
        Z = path.Z[ncol, :]
        s = path.s[ncol, :]
        rk = path.rk[ncol, :]
        s_w = path.s_w[ncol, :]
        psi = path.psi[ncol, :]
        # nu = path.nu[ncol, :]
        # Theta = path.Theta[ncol, :]
        p_eq = path.p_eq[ncol, :]
        p_share = path.p_share[ncol, :]
        p_k = path.p_k[ncol, :]
        Div_k = path.Div_k[ncol, :]
        p_int = path.p_int[ncol, :]
        Div_int = path.Div_int[ncol, :]
        c = path.c
        a = path.a
        D = path.D

        #################
        # implied paths #
        #################


        A_target = (par.hh_wealth_Y_ratio - par.L_Y_ratio)*ss.Y
        for t in range(par.T):
            A_lag = A[t - 1] if t > 0 else ini.A
            da = ss.r / (1 + ss.r) * (1 + ra[t]) * a[t] + par.chi * ((1 + ra[t]) * a[t] - (1 + ss.r) * A_target)
            d_agg = np.sum(da * D[t])
            A[t] = (1 + ra[t]) * A_lag - d_agg

        L[:] = hh_wealth - A



        for t in range(par.T):
            # A_lag = A[t - 1] if t > 0 else ini.A
            L_lag = L[t - 1] if t > 0 else ini.L
            # rl_lag = rl[t - 1] if t > 0 else ini.rl
            C[t] = Y[t] - G[t] - I[t] - psi[t] - par.xi * L_lag
            # C[t] = (1 + rl_lag) * L_lag + (1 + ra[t]) * A_lag + (1 - tau[t]) * w[t] * N[t] - A[t] - L[t]



        # a. NKPC-wage
        for t_ in range(par.T):
            t = (par.T - 1) - t_
            u_prime_e = integrate_marg_util(c[t], D[t], par.z_grid, par.sigma)
            s_w[t] = par.nu * N[t] ** (1/par.frisch) / ( (1 - tau[t]) * w[t] * u_prime_e)

            Pi_w_plus = Pi_w[t + 1] if t < par.T - 1 else ss.Pi_w
            Pi[t] = bisection(NKPC_w_eq, -0.2, 0.2, args=(par, s_w[t], Pi_w_plus))

        # total household wealth
        # hh_wealth[:] = A_hh + L_hh



        ###########
        # targets #
        ###########

        # a. Fisher equation
        for t_ in range(par.T):
            t = (par.T - 1) - t_
            Pi_w_plus = Pi_w[t + 1] if t < par.T - 1 else ss.Pi_w
            fisher_res[t] = 1 + i[t] - (1 + r[t]) * (1 + Pi_w_plus)

        # b. Good market clearing
        for t in range(par.T):
            L_hh_lag = L_hh[t - 1] if t > 0 else ini.L_hh
            # C[t] = Y[t] - G[t] - I[t] - I[t] * 0 - par.xi * L_hh_lag
            clearing_Y[t] = C_hh[t] + I[t] + G[t] + psi[t] + par.xi * L_hh_lag - Y[t]

        # c. wage residual
        for t in range(par.T):
            w_lag = w[t - 1] if t > 0 else ini.w
            w_res[t] = np.log(w[t] / w_lag) - Pi_w[t] + Pi[t]










