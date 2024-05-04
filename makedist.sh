#!/bin/bash
########################################################################
### @file makedist.sh
### @brief Make a distribution archive of the SCPI Server
########################################################################

progname=${0##*/}
srcdirs=(".")
dstdir=${PWD}/..

srcdirs=(".")
for folderspec in ".folders" ".folders.default"
do
    if [ -f "${folderspec}" ]
    then
        srcdirs=()
        exec < "${folderspec}"
        while read line; do
            text=$(echo ${line%%#*})
            [ "${text}" ] && srcdirs=("${text}" "${srcdirs[@]}")
        done
        break
    fi
done


usage()
{
    [ "$1" ] && echo "${progrname}: $*" >&2
    echo "Usage: ${progname} [-build=<build>] [-suffix=<suffix>] [-stdout] [<version>]" >&2
    exit 1
}

packall()
{

    name=SCPIServer
    product=$1 ; shift
    file=$1    ; shift

    case $(uname -s) in
	Darwin)   tmpfolder=/private$(mktemp -d -t makedist)
                  taropts=()
                  ;;
        Linux)    tmpfolder=$(mktemp -d)
                  taropts=("--owner=0" "--group=0")
                  ;;
        *)        tmpfolder=/tmp/makedist.$$;
                  mkdir -p ${tmpfolder}
                  taropts=()
                  ;;
    esac

    for dir in "${srcdirs[@]}"
    do
        if [ -d "${dir}" ]
        then
            (
                cd "${dir}"
                echo "  - Adding files from ${PWD}..." >&2
                find . "${@}" -print0 2>/dev/null | cpio -pmud0 --quiet "${tmpfolder}/${name}"

                pfolder="Products/${product}"
                if [ -d "${pfolder}" ]
                then
                   cd "${pfolder}"
                   echo "  - Adding product-specific files from ${PWD}..." >&2
                   find . "${@}" -print0 2>/dev/null | cpio -pmud0 --quiet "${tmpfolder}/${name}"
                fi
            )
        fi
    done

    cd "${tmpfolder}"
    tar -c -z ${taropts[@]} -f "${file}" "${name}"
    cd ..
    rm -r "${tmpfolder}"
}



product=""
build=""
version=""
suffix=""
modify=false
vfile=Config/version.ini
archive=""
symlink=""

while [ "$1" ]
do
  case "$1" in
      -product=*)
          product=${1#-product=}
          modify=true
          ;;

      -build=*)
	  build=${1#-build=}
          modify=true
	  ;;

      -suffix=*)
          suffix="-${1#-suffix=}"
          ;;

      -output=*)
          archive="${1#-output=}"
	  ;;

      -stdout)
	  archive="-"
	  ;;

      -symlink=*)
	  symlink="${1#-symlink=}"
	  ;;


      -help)
	  usage
	  ;;

      -*)
	  usage "Invalid option: $1"
	  ;;

      *)
          version="$1"
          modify=true
	  ;;

  esac
  shift
done


### Update version/build number
[ "${product}" ] || product=$(sed -n 's/product *= *\(\.*\)/\1/p' "${vfile}")
[ "${version}" ] || version=$(sed -n 's/version *= *\(.*\)/\1/p' "${vfile}")
#[ "${build}"   ] || build=$(sed -n 's/build *= *\(.*\)/\1/p' "${vfile}")

if ${modify}
then
    sed -e "s/product *=.*/product = ${product}/g" \
        -e "s/version *=.*/version = ${version}/g" \
        -e "s/build *=.*/build = ${build}/g" -i "${vfile}"
fi

if [ ! "${archive}" ]
then
    filename="scpiserver-${product,,}-${version}${suffix}.tar.gz"
    archive="${dstdir}/${filename}"
fi

echo "Creating: -product='${product}' -version='${version}' -build='${build}' -archive='${archive}':" >&2

## Byte-compile python source into ".pyc" files -- these are specific to Python version.
#echo "### Byte-compiling python source..."
#find "${srcdirs[@]}" -name '*.py' -print0 | xargs -0 py_compilefiles


packall "${product}" "${archive}" \
    '(' -name UnitTest -o -name Documentation -o -name Extensions -o -name '__pycache__' ')' -prune -o \
    '(' -name '*.sh' -o -name '*.bat' -o -name '*.so' -o -name '*.mod' -o -name '*.scpi' -o -name '*.ini' \
    -o -name '*.py' -o -name '*.txt' -o -name '*.dll' -o -name '*.bin' -o -name '*.pem' \
    -o -name '*.zip' -o -name '*.gz' -o -name '.attributes' -o -path './Scripts/*' ')'

if [ ${symlink} ]
then
    (cd $(dirname "${archive}") && ln -s $(basename "${archive}") ${symlink})
fi
