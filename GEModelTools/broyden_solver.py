# contains a broyden solver for equation systems

import numpy as np

def broyden_solver(f,x0,jac,
    tol=1e-8,max_iter=100,backtrack_fac=0.5,max_backtrack=30,
    do_print=False,do_print_unknowns=False,model=None,
    fixed_jac=False):
    """ numerical solver using the broyden method """

    # a. initial
    x = x0.ravel()
    y = f(x)

    if len(x) < len(y) and do_print:
        print("Dimension of x, is less than dimension of y."
              " Using least-squares criterion to solve for approximate root.")


    # b. iterate
    for it in range(max_iter):
        
        # i. current difference
        abs_diff = np.max(np.abs(y))
        if do_print: 
            
            print(f' it = {it:3d} -> max. abs. error = {abs_diff:8.2e}')

            if not model is None and do_print_unknowns:
                for unknown in model.unknowns:
                    minval = np.min(model.path.__dict__[unknown][0,:])
                    meanval = np.mean(model.path.__dict__[unknown][0,:])
                    maxval = np.max(model.path.__dict__[unknown][0,:])
                    print(f'   {unknown:15s}: {minval = :7.3f} {meanval = :7.3f} {maxval = :7.3f}')
     
            if not model is None and len(model.targets) > 1:
                y_ = y.reshape((len(model.targets),-1))
                for i,target in enumerate(model.targets):
                    print(f'   {np.max(np.abs(y_[i])):8.2e} in {target}')

        if abs_diff < tol: return x
        
        # ii. new x
        if len(x) == len(y):
            dx = np.linalg.solve(jac, -y)
        elif len(x) < len(y):
            dx = np.linalg.lstsq(jac, -y, rcond=None)[0]  # not allowed to use rcond=None in Numba
        else:
            raise ValueError("Dimension of x is greater than dimension of y."
                             " Cannot solve underdetermined system.")

        # iii. evalute with backtrack
        for _ in range(max_backtrack):

            try: # evaluate
                ynew = f(x+dx)
                if np.any(np.isnan(ynew)): raise ValueError('found nan value')
            except Exception as e: # backtrack
                if do_print: print(f'backtracking...')
                dx *= backtrack_fac
            else: # update jac and break from backtracking
                dy = ynew-y
                if not fixed_jac:
                    jac = jac + np.outer(((dy - jac @ dx) / np.linalg.norm(dx) ** 2), dx)
                y = ynew
                x += dx
                break

        else:

            raise ValueError(f'GEModelTools: Number of backtracks exceeds {max_backtrack}')

    else:

        raise ValueError(f'GEModelTools: No convergence after {max_iter} iterations with broyden_solver(tol={tol:.1e})')    