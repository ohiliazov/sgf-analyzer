**Leela** available arguments:

    -g [ --gtp ]                  Enable GTP mode.
    --noponder                    Disable thinking on opponent's time.

    -h [ --help ]                 Show commandline options.
    -t [ --threads ] arg (=4)     Number of threads to use.
    -p [ --playouts ] arg         Weaken engine by limiting the number of 
                                playouts. Requires --noponder.
    -b [ --lagbuffer ] arg (=100) Safety margin for time usage in centiseconds.
    -l [ --logfile ] arg          File to log input/output to.
    -q [ --quiet ]                Disable all diagnostic output.
    -k [ --komiadjust ]           Adjust komi one point in my disadvantage (for 
                                territory scoring).
    --nonets                      Disable use of neural networks.
    --nobook                      Disable use of the fuseki library.
    --gpu arg                     ID of the OpenCL device(s) to use (disables 
                                autodetection).
    --rowtiles arg (=5)           Split up the board in # tiles.

**Leela Zero** available arguments:

    -g [ --gtp ]                  Enable GTP mode.
    --noponder                    Disable thinking on opponent's time.
    
    -h [ --help ]                 Show commandline options.
    -t [ --threads ] arg (=2)     Number of threads to use.
    -p [ --playouts ] arg         Weaken engine by limiting the number of
                                playouts.Requires --noponder.
    -v [ --visits ] arg           Weaken engine by limiting the number of visits.
    --timemanage arg (=auto)      [auto|on|off] Enable extra time management
                                features.
                                auto = off when using -m, otherwise on
    -b [ --lagbuffer ] arg (=100) Safety margin for time usage in centiseconds.
    -r [ --resignpct ] arg (=-1)  Resign when winrate is less than x%.
                                -1 uses 10% but scales for handicap.
    -m [ --randomcnt ] arg (=0)   Play more randomly the first x moves.
    -n [ --noise ]                Enable policy network randomization.
    -s [ --seed ] arg             Random number generation seed.
    -d [ --dumbpass ]             Don't use heuristics for smarter passing.
    -w [ --weights ] arg          File with network weights.
    -l [ --logfile ] arg          File to log input/output to.
    -q [ --quiet ]                Disable all diagnostic output.
    --gpu arg                     ID of the OpenCL device(s) to use (disables
                                autodetection).
    --full-tuner                  Try harder to find an optimal OpenCL tuning.
    --tune-only                   Tune OpenCL only and then exit.