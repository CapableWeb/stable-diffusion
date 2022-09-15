"""Helper class for dealing with image generation arguments.

The Args class parses both the command line (shell) arguments, as well as the
command string passed at the dream> prompt. It serves as the definitive repository
of all the arguments used by Generate and their default values.

To use:
  a = Args()

  # read in the command line options:
  args = a.parse_args()

  # read in a command passed to the dream> prompt:
  opts = a.parse_cmd('do androids dream of electric sheep? -H256 -W1024 -n4')

  # The args object acts like a namespace object
  print(a.model)

You can set attributes in the usual way, use vars(), etc.:

  a.model = 'something-else'
  do_something(**vars(a))

It is helpful in saving metadata:

  # To get a json representation of all the values, allowing
  # you to override any values dynamically
  j = a.json(seed=42)

  # To get the prompt string with the switches, allowing you
  # to override any values dynamically
  j = a.prompt_str(seed=42)

If you want to access the namespace objects from the shell args or the
parsed command directly, you may use the values returned from the
original calls to parse_args() and parse_cmd(), or get them later
using the _arg_switches and _cmd_switches attributes. This can be
useful if both the args and the command contain the same attribute and
you wish to apply logic as to which one to use. For example:

  a = Args()
  args    = a.parse_args()
  opts    = a.parse_cmd(string)
  do_grid = args.grid or opts.grid

To add new attributes, edit the _create_command_arg_parser() and
_create_cmd_parser() methods.

We also export the function build_metadata
"""

import argparse
import shlex
import json

SAMPLER_CHOICES = [
    'ddim',
    'k_dpm_2_a',
    'k_dpm_2',
    'k_euler_a',
    'k_euler',
    'k_heun',
    'k_lms',
    'plms',
]

# is there a way to pick this up during git commits?
APP_ID      = 'lstein/stable-diffusion'
APP_VERSION = 'v1.15'

class Args(object):
    def __init__(self):
        '''Initialize new Args class. Takes no arguments'''
        self._arg_parser   = self._create_arg_parser()
        self._cmd_parser   = self._create_cmd_parser()
        self._arg_switches = self.parse_args()   # so there's something there
        self._cmd_switches = self.parse_cmd('')  # so there's something there

    def parse_args(self):
        '''Parse the shell switches and store.'''
        self._arg_switches = self._arg_parser.parse_args()
        return self._arg_switches

    def parse_cmd(self,cmd_string):
        '''Parse a dream>-style command string '''
        command = cmd_string.replace("'", "\\'")
        try:
            elements = shlex.split(command)
        except ValueError:
            print(traceback.format_exc(), file=sys.stderr)
            return
        switches = ['']
        switches_started = False

        for el in elements:
            if el[0] == '-' and not switches_started:
                switches_started = True
            if switches_started:
                switches.append(el)
            else:
                switches[0] += el
                switches[0] += ' '
        switches[0] = switches[0][: len(switches[0]) - 1]
        self._cmd_switches = self._cmd_parser.parse_args(switches)
        return self._cmd_switches

    def json(self,**kwargs):
        return json.dumps(self.to_dict(**kwargs))

    def to_dict(self,**kwargs):
        a = vars(self)
        a.update(kwargs)
        return a

    # Isn't there a more automated way of doing this?
    # Ideally we get the switch strings out of the argparse objects,
    # but I don't see a documented API for this.
    def prompt_str(self,**kwargs):
        """Normalized prompt."""
        a = vars(self)
        a.update(kwargs)
        switches = list()
        switches.append(f'"{a["prompt"]}')
        switches.append(f'-s {a["steps"]}')
        switches.append(f'-W {a["width"]}')
        switches.append(f'-H {a["height"]}')
        switches.append(f'-C {a["cfg_scale"]}')
        switches.append(f'-A {a["sampler_name"]}')
        switches.append(f'-S {a["seed"]}')
        if a['seamless']:
            switches.append(f'--seamless')
        if len(a['init_img'])>0:
            switches.append(f'-I {a.init_img}')
        if a['fit']:
            switches.append(f'--fit')
        if a['strength'] and len(a['init_img'])>0:
            switches.append(f'-f {a["strength"]}')
        if a['gfpgan_strength']:
            switches.append(f'-G {a["gfpgan_strength"]}')
        if a['upscale']:
            switches.append(f'-U {" ".join([str(u) for u in a["upscale"]])}')
        if a['embiggen']:
            switches.append(f'--embiggen {" ".join([str(u) for u in a["embiggen"]])}')
        if a['embiggen_tiles']:
            switches.append(f'--embiggen_tiles {" ".join([str(u) for u in a["embiggen_tiles"]])}')
        if a['variation_amount'] > 0:
            switches.append(f'-v {a["variation_amount"]}')
        if a['with_variations']:
            formatted_variations = ','.join(f'{seed}:{weight}' for seed, weight in (a["with_variations"]))
            switches.append(f'-V {formatted_variations}')
        return ' '.join(switches)


    def __getattribute__(self,name):
        if name=='__dict__':
            a = self._arg_switches.__dict__
            a.update(self._cmd_switches.__dict__)
            return a
        try:
            return object.__getattribute__(self,name)
        except AttributeError:
            pass
        if self._cmd_switches and hasattr(self._cmd_switches,name):
            return getattr(self._cmd_switches,name)
        elif self._arg_switches and hasattr(self._arg_switches,name):
            return getattr(self._arg_switches,name)
        else:
            raise AttributeError

    def __setattr__(self,name,value):
        if name.startswith('_'):
            object.__setattr__(self,name,value)
        else:
            self._cmd_switches.__dict__[name] = value

    def _create_arg_parser(self):
        '''
        This defines all the arguments used on the command line when you launch
        the CLI or web backend.
        '''
        parser = argparse.ArgumentParser(
            description=
            """
            Generate images using Stable Diffusion.
            Use --web to launch the web interface. 
            Use --from_file to load prompts from a file path or standard input ("-").
            Otherwise you will be dropped into an interactive command prompt (type -h for help.)
            Other command-line arguments are defaults that can usually be overridden
            prompt the command prompt.
            """
        )
        parser.add_argument('--laion400m') # deprecated
        parser.add_argument('--weights') # deprecated
        parser.add_argument(
            '--conf',
            '-c',
            '-conf',
            dest='conf',
            default='./configs/models.yaml',
            help='Path to configuration file for alternate models.',
        )
        parser.add_argument(
            '--model',
            default='stable-diffusion-1.4',
            help='Indicates which diffusion model to load. (currently "stable-diffusion-1.4" (default) or "laion400m")',
        )
        parser.add_argument(
            '--from_file',
            dest='infile',
            type=str,
            help='If specified, load prompts from this file',
        )
        parser.add_argument(
            '-F',
            '--full_precision',
            dest='full_precision',
            action='store_true',
            help='Use more memory-intensive full precision math for calculations',
        )
        parser.add_argument(
            '--outdir',
            '-o',
            type=str,
            help='Directory to save generated images and a log of prompts and seeds. Default: outputs/img-samples',
            default='outputs/img-samples',
        )
        parser.add_argument(
            '--seamless',
            action='store_true',
            help='Change the model to seamless tiling (circular) mode',
        )
        parser.add_argument(
            '--grid',
            '-g',
            action='store_true',
            help='generate a grid'
        )
        parser.add_argument(
            '--embedding_path',
            type=str,
            help='Path to a pre-trained embedding manager checkpoint - can only be set on command line',
        )
        parser.add_argument(
            '--prompt_as_dir',
            '-p',
            action='store_true',
            help='Place images in subdirectories named after the prompt.',
        )
        # GFPGAN related args
        parser.add_argument(
            '--gfpgan_bg_upsampler',
            type=str,
            default='realesrgan',
            help='Background upsampler. Default: realesrgan. Options: realesrgan, none.',

        )
        parser.add_argument(
            '--gfpgan_bg_tile',
            type=int,
            default=400,
            help='Tile size for background sampler, 0 for no tile during testing. Default: 400.',
        )
        parser.add_argument(
            '--gfpgan_model_path',
            type=str,
            default='experiments/pretrained_models/GFPGANv1.3.pth',
            help='Indicates the path to the GFPGAN model, relative to --gfpgan_dir.',
        )
        parser.add_argument(
            '--gfpgan_dir',
            type=str,
            default='./src/gfpgan',
            help='Indicates the directory containing the GFPGAN code.',
        )
        parser.add_argument(
            '--web',
            dest='web',
            action='store_true',
            help='Start in web server mode.',
        )
        parser.add_argument(
            '--host',
            type=str,
            default='127.0.0.1',
            help='Web server: Host or IP to listen on. Set to 0.0.0.0 to accept traffic from other devices on your network.'
        )
        parser.add_argument(
            '--port',
            type=int,
            default='9090',
            help='Web server: Port to listen on'
        )
        return parser

    def _create_cmd_parser(self):
        parser = argparse.ArgumentParser(
            description='Example: dream> a fantastic alien landscape -W1024 -H960 -s100 -n12'
        )
        parser.add_argument('prompt')
        parser.add_argument(
            '-s',
            '--steps',
            type=int,
            default=50,
            help='Number of steps'
        )
        parser.add_argument(
            '-S',
            '--seed',
            type=int,
            default=None,
            help='Image seed; a +ve integer, or use -1 for the previous seed, -2 for the one before that, etc',
        )
        parser.add_argument(
            '-n',
            '--iterations',
            type=int,
            default=1,
            help='Number of samplings to perform (slower, but will provide seeds for individual images)',
        )
        parser.add_argument(
            '-W',
            '--width',
            type=int,
            help='Image width, multiple of 64',
            default=512
        )
        parser.add_argument(
            '-H',
            '--height',
            type=int,
            help='Image height, multiple of 64',
            default=512,
        )
        parser.add_argument(
            '-C',
            '--cfg_scale',
            default=7.5,
            type=float,
            help='Classifier free guidance (CFG) scale - higher numbers cause generator to "try" harder.',
        )
        parser.add_argument(
            '--grid',
            '-g',
            action='store_true',
            help='generate a grid'
        )
        parser.add_argument(
            '--outdir',
            '-o',
            type=str,
            default='outputs/img-samples',
            help='Directory to save generated images and a log of prompts and seeds',
        )
        parser.add_argument(
            '--seamless',
            action='store_true',
            help='Change the model to seamless tiling (circular) mode',
        )
        parser.add_argument(
            '-i',
            '--individual',
            action='store_true',
            help='Generate individual files (default)',
        )
        parser.add_argument(
            '-I',
            '--init_img',
            type=str,
            help='Path to input image for img2img mode (supersedes width and height)',
            default='',
        )
        parser.add_argument(
            '-M',
            '--init_mask',
            type=str,
            help='Path to input mask for inpainting mode (supersedes width and height)',
            default='',
        )
        parser.add_argument(
            '-T',
            '-fit',
            '--fit',
            action='store_true',
            help='If specified, will resize the input image to fit within the dimensions of width x height (512x512 default)',
        )
        parser.add_argument(
            '-f',
            '--strength',
            type=float,
            help='Strength for noising/unnoising. 0.0 preserves image exactly, 1.0 replaces it completely',
            default=0.75,
        )
        parser.add_argument(
            '-G',
            '--gfpgan_strength',
            type=float,
            help='The strength at which to apply the GFPGAN model to the result, in order to improve faces.',
            default=0,
        )
        parser.add_argument(
            '-U',
            '--upscale',
            nargs='+',
            type=float,
            help='Scale factor (2, 4) for upscaling final output followed by upscaling strength (0-1.0). If strength not specified, defaults to 0.75',
            default=None,
        )
        parser.add_argument(
            '--save_original',
            '-save_orig',
            action='store_true',
            help='Save original. Use it when upscaling to save both versions.',
        )
        parser.add_argument(
            '--embiggen',
            '-embiggen',
            nargs='+',
            type=float,
            help='Embiggen tiled img2img for higher resolution and detail without extra VRAM usage. Takes scale factor relative to the size of the --init_img (-I), followed by ESRGAN upscaling strength (0-1.0), followed by minimum amount of overlap between tiles as a decimal ratio (0 - 1.0) or number of pixels. ESRGAN strength defaults to 0.75, and overlap defaults to 0.25 . ESRGAN is used to upscale the init prior to cutting it into tiles/pieces to run through img2img and then stitch back togeather.',
            default=None,
        )
        parser.add_argument(
            '--embiggen_tiles',
            '-embiggen_tiles',
            nargs='+',
            type=int,
            help='If while doing Embiggen we are altering only parts of the image, takes a list of tiles by number to process and replace onto the image e.g. `1 3 5`, useful for redoing problematic spots from a prior Embiggen run',
            default=None,
        )
        parser.add_argument(
            '-x',
            '--skip_normalize',
            action='store_true',
            help='Skip subprompt weight normalization',
        )
        parser.add_argument(
            '-A',
            '-m',
            '--sampler',
            dest='sampler_name',
            type=str,
            choices=SAMPLER_CHOICES,
            metavar='SAMPLER_NAME',
            help=f'Switch to a different sampler. Supported samplers: {", ".join(SAMPLER_CHOICES)}',
            default='k_lms',
        )
        parser.add_argument(
            '-t',
            '--log_tokenization',
            action='store_true',
            help='shows how the prompt is split into tokens'
        )
        parser.add_argument(
            '-v',
            '--variation_amount',
            default=0.0,
            type=float,
            help='If > 0, generates variations on the initial seed instead of random seeds per iteration. Must be between 0 and 1. Higher values will be more different.'
        )
        parser.add_argument(
            '-V',
            '--with_variations',
            default=None,
            type=str,
            help='list of variations to apply, in the format `seed:weight,seed:weight,...'
        )
        return parser

# very partial implementation of https://github.com/lstein/stable-diffusion/issues/266
# it does not write all the required top-level metadata, writes too much image
# data, and doesn't support grids yet. But you gotta start somewhere, no?
def format_metadata(opt):
    '''
    Given an Args object, returns a partial implementation of
    the stable diffusion metadata standard
    '''
    return {
        'model'       : 'stable diffusion',
        'model_id'    : opt.model,
        'app_id'      : APP_ID,
        'app_version' : APP_VERSION,
        'image'       : opt.to_dict()
    }

