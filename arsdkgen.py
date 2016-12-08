#!/usr/bin/env python
import sys, os, stat, logging, tempfile, filecmp, shutil
import optparse
import arsdkparser
#===============================================================================
#===============================================================================

#===============================================================================
# Writer class to wrap a file and allow printf-like write method.
#===============================================================================
class Writer(object):
	def __init__(self, filePath):
		# unlink previous file
		try:
			os.unlink(filePath)
		except OSError as e:
			if e.errno == 2:  # No such file or directory
				pass
			else:
				raise e

		self.filePath = filePath
		self.fd = open(filePath, "w")
	def write(self, fmt, *args):
		if args:
			self.fd.write(fmt % (args))
		else:
			self.fd.write(fmt % ())

	def close(self):
		# close file
		self.fd.close()
		# mark file as readonly
		os.chmod(self.filePath, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

#===============================================================================
#===============================================================================
def main():
	(options, args) = parseArgs()
	setupLog(options)
	generator_filepath = args[0]
	extra = ' '.join(args[1:]) if len(args) > 1 else None

	# Setup full path of output directories
	options.outdir = os.path.abspath(options.outdir)

	logging.info("arsdkgen: cmd=%s generator=%s, outdir=%s extra=%s",
		"list" if options.listFiles else "generate",
		generator_filepath, options.outdir, extra)
	if not options.listFiles and not os.path.exists(options.outdir):
		os.makedirs(options.outdir, 0755)

	# Import package of ge generation
	(generator_path, generator_filename) = os.path.split(generator_filepath)
	sys.path.append(generator_path)
	try:
		generator = __import__(os.path.splitext(generator_filename)[0])
	except ImportError:
		logging.error("Unable to import generator %s", generator_filepath)
		sys.exit(1)

	ctx = arsdkparser.ArParserCtx()
	path, filename = os.path.split(os.path.realpath(__file__))
	path = os.path.join(path, "xml")
	# first load generic.xml
	arsdkparser.parse_xml(ctx, os.path.join(path, "generic.xml"))
	for f in sorted(os.listdir(path)):
		if not f.endswith(".xml") or f == "generic.xml":
			continue
		arsdkparser.parse_xml(ctx, os.path.join(path, f))

	# Finalize features after parsing
	arsdkparser.finalize_ftrs(ctx)

	# Call generator
	if options.listFiles:
		generator.list_files(ctx, options.outdir, extra)
	else:
		# Generate in tmp folder.
		tmp_dir = tempfile.mkdtemp()
		generator.generate_files(ctx, tmp_dir, extra)
		# Copy in outdir all files different in tmp_dir and in outdir.
		for path, subdirs, files in os.walk(tmp_dir):
			for name in files:
				f_tmp = os.path.join(path, name)
				f_cp = f_tmp.replace(tmp_dir, options.outdir)
				if not os.path.isfile(f_cp) or \
						filecmp.cmp(f_tmp, f_cp) == False:
					if not os.path.exists(os.path.dirname(f_cp)):
						os.makedirs(os.path.dirname(f_cp))
					logging.info('Copy: ' + f_tmp + " => " + f_cp)
					shutil.copy(f_tmp, f_cp)
		# Remove tmp_dir
		shutil.rmtree(tmp_dir)

#===============================================================================
# Setup option parser and parse command line.
#===============================================================================
def parseArgs():
	# Setup parser
	usage = "usage: %prog [options] <generator> [extra]"
	parser = optparse.OptionParser(usage = usage)

	# Main options
	parser.add_option("-o", "--output",
		dest = "outdir",
		action = "store",
		default = ".",
		metavar = "DIR",
		help = "Name of output directory [default: current directory]")
	parser.add_option("-f", "--files",
		dest = "listFiles",
		action = "store_true",
		default = False,
		help = "List on stdout full path of files that will be generated and exit")

	# Other options
	parser.add_option("-q",
		dest = "quiet",
		action = "store_true",
		default = False,
		help = "be quiet")
	parser.add_option("-v",
		dest = "verbose",
		action = "count",
		default = 0,
		help = "verbose output (more verbose if specified twice)")

	# Parse arguments and check validity
	(options, args) = parser.parse_args()

	if len(args) < 1:
		parser.error("Missing generator filepath")

	return (options, args)

#===============================================================================
# Setup logging system.
#===============================================================================
def setupLog(options):
	logging.basicConfig(
		level = logging.WARNING,
		format = "[%(levelname)s] %(message)s",
		stream = sys.stderr)
	logging.addLevelName(logging.CRITICAL, "C")
	logging.addLevelName(logging.ERROR, "E")
	logging.addLevelName(logging.WARNING, "W")
	logging.addLevelName(logging.INFO, "I")
	logging.addLevelName(logging.DEBUG, "D")

	# Setup log level
	if options.quiet == True:
		logging.getLogger().setLevel(logging.CRITICAL)
	elif options.verbose >= 2:
		logging.getLogger().setLevel(logging.DEBUG)
	elif options.verbose >= 1:
		logging.getLogger().setLevel(logging.INFO)

#===============================================================================
#===============================================================================
if __name__ == "__main__":
	main()
