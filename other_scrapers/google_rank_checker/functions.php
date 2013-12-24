<?php
/* License: open source for private and commercial use
   This code is free to use and modify as long as this comment stays untouched on top.
   URL of original source: http://google-rank-checker.squabbel.com
   Author of original source: justone@squabbel.com
   This tool should be completely legal but in any case you may not sue or seek compensation from the original Author for any damages or legal issues the use may cause.
   By using this source code you agree NOT to increase the request rates beyond the IP management function limitations, this would only harm our common cause.
 */
function verbose($text)
{
	echo $text;
}

/*
 * By default (no force) the function will load cached data within 24 hours otherwise reject the cache.
 * Google does not change its ranking too frequently, that's why 24 hours has been chosen.
 *
 * Multithreading: When multithreading you need to work on a proper locking mechanism
 */
function load_cache($search_string,$page,$country_data,$force_cache)
{
	global $working_dir;
	global $NL;
	global $test_100_resultpage;
	
	if ($force_cache < 0) return NULL;
	$lc=$country_data['lc'];
	$cc=$country_data['cc'];
	if ($test_100_resultpage)
		$hash=md5($search_string."_".$lc."_".$cc.".".$page.".100p");
	else
		$hash=md5($search_string."_".$lc."_".$cc.".".$page);
	$file="$working_dir/$hash.cache";
	$now=time();
	if (file_exists($file))
	{
		$ut=filemtime($file);
		$dif=$now-$ut;
		$hour=(int)($dif/(60*60));
		if ($force_cache || ($dif < (60*60*24)))
		{
			$serdata=file_get_contents($file);
			$serp_data=unserialize($serdata);
			verbose("Cache: loaded file $file for $search_string and page $page. File age: $hour hours$NL");
			return $serp_data;
		}
		return NULL;
	} else
	 return NULL;

}

/*
 * Multithreading: When multithreading you need to work on a proper locking mechanism
 */
function store_cache($serp_data,$search_string,$page,$country_data)
{
	global $working_dir;
	global $NL;
	global $test_100_resultpage;
	
	$lc=$country_data['lc'];
	$cc=$country_data['cc'];
	if ($test_100_resultpage)
		$hash=md5($search_string."_".$lc."_".$cc.".".$page.".100p");
	else
		$hash=md5($search_string."_".$lc."_".$cc.".".$page);
	$file="$working_dir/$hash.cache";
	$now=time();
	if (file_exists($file))
	{
		$ut=filemtime($file);
		$dif=$now-$ut;
		if ($dif < (60*60*24)) echo "Warning: cache storage initated for $search_string page $page which was already cached within the past 24 hours!$NL";
	}
	$serdata=serialize($serp_data);
	file_put_contents($file,$serdata, LOCK_EX);
	verbose("Cache: stored file $file for $search_string and page $page.$NL");
}

// check_ip_usage() must be called before first use of mark_ip_usage()
function check_ip_usage()
{
	global $PROXY;
	global $working_dir;
	global $NL;
	global $ip_usage_data; // usage data object as array
	
	if (!isset($PROXY['ready'])) return 0; // proxy not ready/started
	if (!$PROXY['ready']) return 0; // proxy not ready/started
	
	if (!isset($ip_usage_data))
	{
		if (!file_exists($working_dir."/ipdata.obj")) // usage data object as file
		{
			echo "Warning!$NL"."The ipdata.obj file was not found, if this is the first usage of the rank checker everything is alright.$NL"."Otherwise removal or failure to access the ip usage data will lead to damage of the IP quality.$NL$NL";
			sleep(5);
			$ip_usage_data=array();
		} else
		{
			$ser_data=file_get_contents($working_dir."/ipdata.obj");
			$ip_usage_data=unserialize($ser_data);
		}
	}
	
	if (!isset($ip_usage_data[$PROXY['external_ip']])) 
	{
		verbose("IP $PROXY[external_ip] is ready for use $NL");
		return 1; // the IP was not used yet
	}
	if (!isset($ip_usage_data[$PROXY['external_ip']]['requests'][20]['ut_google'])) 
	{
		verbose("IP $PROXY[external_ip] is ready for use $NL");
		return 1; // the IP has not been used 20+ times yet, return true
	}
	$ut_last=(int)$ip_usage_data[$PROXY['external_ip']]['ut_last-usage']; // last time this IP was used
	$req_total=(int)$ip_usage_data[$PROXY['external_ip']]['request-total']; // total number of requests made by this IP
	$req_20=(int)$ip_usage_data[$PROXY['external_ip']]['requests'][20]['ut_google']; // the 20th request (if IP was used 20+ times) unixtime stamp
	
	$now=time();
	if (($now - $req_20) > (60*60) ) 
	{
		verbose("IP $PROXY[external_ip] is ready for use $NL");
		return 1; // more than an hour passed since 20th usage of this IP
	} else
	{
		$cd_sec=(60*60) - ($now - $req_20);
		verbose("IP $PROXY[external_ip] needs $cd_sec seconds cooldown, not ready for use yet $NL");
		return 0; // the IP is overused, it can not be used for scraping without being detected by the search engine yet
	}
	
}


// return 1 if license is ready, otherwise 0
function get_license()
{
	global $uid;
	global $pwd;
	global $LICENSE;
	global $NL;
	
	$res=proxy_api("hello"); // will fill $LICENSE
	$ip="";
	if ($res <= 0)
	{
		verbose("API error: Proxy API connection failed (Error $res). trying again soon..$NL$NL");
		return 0;
	} else
	{
		($LICENSE['active']==1) ? $ready="active" : $ready="not active";
		verbose("API success: License is $ready.$NL");
		if ($LICENSE['active']==1) return 1;
		return 0;
	}
	
	return $LICENSE;
}

/* Delay (sleep) based on the license size to allow optimal scraping
 *
 * Warning!
 * Do NOT change the delay to be shorter than the specified delay.
 * When scraping Google you should never do more than 20 requests per hour per IP address
 * This function will create a delay based on your total IP addresses.
 *
 * Together with the IP management functions this will ensure that your IPs stay healthy (no wrong rankings) and undetected (no virus warnings, blacklists, captchas)
 *
 * Multithreading:
 * When multithreading you need to multiply the delay time ($d) by the number of threads
 */
function delay_time()
{
	global $NL;
	global $LICENSE;
	
	$d=(3600*1000000/(((float)$LICENSE['total_ips'])*19.9));
	verbose("Delay based on license size, please wait.. $NL");
	usleep($d);
}

/*
 * Updates and stores the ip usage data object
 * Marks an IP as used and re-sorts the access array 
 */
function mark_ip_usage()
{
	global $PROXY;
	global $working_dir;
	global $NL;
	global $ip_usage_data; // usage data object as array
	
	if (!isset($ip_usage_data)) die("ERROR: Incorrect usage. check_ip_usage() needs to be called once before mark_ip_usage()!$NL");
	$now=time();
	
	$ip_usage_data[$PROXY['external_ip']]['ut_last-usage']=$now; // last time this IP was used
	if (!isset($ip_usage_data[$PROXY['external_ip']]['request-total'])) $ip_usage_data[$PROXY['external_ip']]['request-total']=0;
	$ip_usage_data[$PROXY['external_ip']]['request-total']++; // total number of requests made by this IP
	// shift fifo queue
	for ($req=19;$req>=1;$req--)
	{
		if (isset($ip_usage_data[$PROXY['external_ip']]['requests'][$req]['ut_google']))
		{
			$ip_usage_data[$PROXY['external_ip']]['requests'][$req+1]['ut_google']=$ip_usage_data[$PROXY['external_ip']]['requests'][$req]['ut_google']; 
		}
	}
	$ip_usage_data[$PROXY['external_ip']]['requests'][1]['ut_google']=$now; 
	
	$serdata=serialize($ip_usage_data);
	file_put_contents($working_dir."/ipdata.obj",$serdata, LOCK_EX);
	
}


// access google based on parameters and return raw html or "0" in case of an error
function scrape_serp_google($search_string,$page,$local_data)
{
	global $ch;
	global $NL;
	global $PROXY;
	global $LICENSE;
	global $scrape_result;
	global $test_100_resultpage;
	global $filter;
	$scrape_result="";
	
	$google_ip=$local_data['domain'];
	$hl=$local_data['lc'];
	
	if ($page == 0)
	{
		if ($test_100_resultpage)
			$url="http://$google_ip/search?q=$search_string&hl=$hl&ie=utf-8&as_qdr=all&aq=t&rls=org:mozilla:us:official&client=firefox&num=100&filter=$filter";
		else
			$url="http://$google_ip/search?q=$search_string&hl=$hl&ie=utf-8&as_qdr=all&aq=t&rls=org:mozilla:us:official&client=firefox&num=10&filter=$filter";
	} else
	{
		
		if ($test_100_resultpage)
		{
			$num=$page*100;
			$url="http://$google_ip/search?q=$search_string&hl=$hl&ie=utf-8&as_qdr=all&aq=t&rls=org:mozilla:us:official&client=firefox&start=$num&num=100&filter=$filter";
		} else
		{
			$num=$page*10;
			$url="http://$google_ip/search?q=$search_string&hl=$hl&ie=utf-8&as_qdr=all&aq=t&rls=org:mozilla:us:official&client=firefox&start=$num&num=10&filter=$filter";
		}
	}
	//verbose("Debug, Search URL: $url$NL");
	
	curl_setopt ($ch, CURLOPT_URL, $url);
	$htmdata = curl_exec ($ch);
	if (!$htmdata)
	{
		$error = curl_error($ch);
		$info = curl_getinfo($ch);        
		echo "\tError scraping: $error [ $error ]$NL";
		$scrape_result="SCRAPE_ERROR";
		sleep (3);
		return "";
	} else
	if (strlen($htmdata) < 20)
	{
		$scrape_result="SCRAPE_EMPTY_SERP";
		sleep (3);
		return "";		
	}
	
	
	if (strstr($htmdata,"computer virus or spyware application")) 
	{
		echo("Google blocked us, we need more proxies ! Make sure you did not damage the IP management functions. $NL");
		$scrape_result="SCRAPE_DETECTED";
		die();
	}
	if (strstr($htmdata,"entire network is affected")) 
	{
		echo("Google blocked us, we need more proxies ! Make sure you did not damage the IP management functions. $NL");
		$scrape_result="SCRAPE_DETECTED";
		die();
	}	
	if (strstr($htmdata,"http://www.download.com/Antivirus")) 
	{
		echo("Google blocked us, we need more proxies ! Make sure you did not damage the IP management functions. $NL");
		$scrape_result="SCRAPE_DETECTED";
		die();
	}	
 	if (strstr($htmdata,"/images/yellow_warning.gif"))
	{
		echo("Google blocked us, we need more proxies ! Make sure you did not damage the IP management functions. $NL");
		$scrape_result="SCRAPE_DETECTED";
		die();
	}
	$scrape_result="SCRAPE_SUCCESS";
	return $htmdata;
}


/*
 * Parser
 * This function will parse the Google html code and create the data array with ranking information
 * The variable $process_result will contain general information or warnings/errors
 */
function process_raw($htmdata,$page) // process the html and put results into $serp_data
{
	global $process_result; // contains metainformation from the process_raw() function
	global $test_100_resultpage;
	global $NL;
	global $B;
	global $B_;
	
	
	$dom = new domDocument; 
	$dom->strictErrorChecking = false; 
	$dom->preserveWhiteSpace = true; 
	@$dom->loadHTML($htmdata); 
	$lists=$dom->getElementsByTagName('li'); 
  $num=0;
	
	$results=array();
	foreach ($lists as $list)
	{
		unset($ar);unset($divs);unset($div);unset($cont);unset($result);unset($tmp);
		$ar=dom2array_full($list);			
		if (count($ar) < 2) 
		{
			verbose("s");
			continue; // skipping advertisements
		}
		if ((!isset($ar['class'])) || ($ar['class'] != 'g')) 
		{
			verbose("x");
			continue; // skipping non-search result entries
		}
	
		// adaption to new google layout
		if (isset($ar['div'][1]))
			$ar['div']=&$ar['div'][0];
		if (isset($ar['div'][1]))
			$ar['div']=&$ar['div'][0];
		//$ar=&$ar['div']['span']; // changes 2011 - Google changed layout
		//$ar=&$ar['div']; // changes 2011 - Google changed layout // change again, 2012-2013
		$orig_ar=$ar; // 2012-2013
		// adaption finished
	
		$divs=$list->getElementsByTagName('div');
		$div=$divs->item(1);
		getContent($cont,$div);	
		
		$num++;
		$result['title']=&$ar['h3']['a']['textContent'];
		
		$tmp=strstr(&$ar['h3']['a']['@attributes']['href'],"http");
		$result['url']=$tmp;
		if (strstr(&$ar['h3']['a']['@attributes']['href'],"interstitial")) echo "!";
		
		$tmp=parse_url(&$result['url']);
		$result['host']=&$tmp['host'];

		$desc=strstr($cont,"<span class='st'>"); // instead of using DOM the string is parsed traditional due to frequent layout changes by Google
		$desc=substr($desc,17);
		$desc=strip_tags($desc);
		$result['desc']=$desc;
		
		// 2012-2013 addon, might be extended with on request
		if (isset($ar['table']) && (strlen($result['title'] < 2))) // special mode -  embedded video or similar
		{
			// if interesting the object can be parsed here
			$result['title']="embedded object";
			$result['url']="embedded object";
		}
	
		//echo "$B Result parsed:$B_ $result[title]$NL";
		verbose("r");
		flush();					
		$results[]=$result; // This adds the result to our large result array
	}
	verbose(" !$NL");
  
	// Analyze if more results are available (next page)
	$next=0;
	$tables=$dom->getElementsByTagName('table');
	if (strstr($htmdata,"Next</a>")) $next=1;
	else
	{
		if ($test_100_resultpage)
			$needstart=($page+1)*100;
		else
			$needstart=($page+1)*10;
		$findstr="start=$needstart";
		if (strstr($htmdata,$findstr)) $next=1;
	}
	$page++;
	if ($next) 
	{
		$process_result="PROCESS_SUCCESS_MORE"; // more data available
	} else
		$process_result="PROCESS_SUCCESS_LAST"; // last page reached

	//var_dump($results);

	return $results;
}



function rotate_proxy()
{
	global $PROXY;
	global $ch;
	global $NL;
	$max_errors=3;
	$success=0;
	while ($max_errors--)
	{
		$res=proxy_api("rotate");  // will fill $PROXY
		$ip="";
		if ($res <= 0)
		{
			verbose("API error: Proxy API connection failed (Error $res). trying again soon..$NL$NL");
			sleep(21); // retry after a while
		} else
		{
			verbose("API success: Received proxy IP $PROXY[external_ip] on port $PROXY[port]$NL");
			$success=1;
			break;
		}
	}
	if ($success)
	{
		$ch=new_curl_session($ch);
		return 1;
	} else
		return "API rotation failed. Check license, firewall and API credentials.$NL";
}

/*
 * This is the API function for $portal.seo-proxies.com, currently supporting the "rotate" command
 * On success it will define the $PROXY variable, adding the elements ready,address,port,external_ip and return 1
 * On failure the return is <= 0 and the PROXY variable ready element is set to "0"
 */
function extractBody($response_str)
{
	$parts = preg_split('|(?:\r?\n){2}|m', $response_str, 2);
	if (isset($parts[1])) return $parts[1];
	return '';
}
function proxy_api($cmd,$x="")
{
	global $pwd;
	global $uid;
	global $PROXY;
	global $LICENSE;
	global $NL;
	global $portal;
	$fp = fsockopen("$portal.seo-proxies.com", 80);
	if (!$fp) 
	{
		echo "Unable to connect to proxy API $NL";
		return -1; // connection not possible
	} else 
	{
		if ($cmd == "hello")
		{
			fwrite($fp, "GET /api.php?api=1&uid=$uid&pwd=$pwd&cmd=hello&extended=1 HTTP/1.0\r\nHost: $portal.seo-proxies.com\r\nAccept: text/html, text/plain, text/*, */*;q=0.01\r\nAccept-Encoding: plain\r\nAccept-Language: en\r\n\r\n");
			
					 	stream_set_timeout($fp, 8);
			$res="";
			$n=0;
			while (!feof($fp)) 
			{
				if ($n++ > 4) break;
	  			$res .= fread($fp, 8192);
			}
		 	$info = stream_get_meta_data($fp);
		 	fclose($fp);
		
		 	if ($info['timed_out']) 
			{
				echo 'API: Connection timed out! $NL';
				$LICENSE['active']=0;
				return -2; // api timeout
		  } else 
			{
				if (strlen($res) > 1000) return -3; // invalid api response (check the API website for possible problems)
				$data=extractBody($res);
				$ar=explode(":",$data);
				if (count($ar) < 4) return -100; // invalid api response
				switch ($ar[0])
				{
					case "ERROR":
						echo "API Error: $res $NL";
						$LICENSE['active']=0;
						return 0; // Error received
					break;
					case "HELLO":
					  $LICENSE['max_ips']=$ar[1]; 	// number of IPs licensed
						$LICENSE['total_ips']=$ar[2]; // number of IPs assigned
						$LICENSE['protocol']=$ar[3]; 	// current proxy protocol (http, socks, vpn)
						$LICENSE['processes']=$ar[4]; // number of proxy processes
						if ($LICENSE['total_ips'] > 0) $LICENSE['active']=1; else $LICENSE['active']=0;
						return 1;
					break;
					default:
						echo "API Error: Received answer $ar[0], expected \"HELLO\"";
						$LICENSE['active']=0;
						return -101; // unknown API response
				}
			}
			
		} // cmd==hello
		
		
		
		if ($cmd == "rotate")
		{
			$PROXY['ready']=0;
			fwrite($fp, "GET /api.php?api=1&uid=$uid&pwd=$pwd&cmd=rotate&randomness=0&offset=0 HTTP/1.0\r\nHost: $portal.seo-proxies.com\r\nAccept: text/html, text/plain, text/*, */*;q=0.01\r\nAccept-Encoding: plain\r\nAccept-Language: en\r\n\r\n");
		 	stream_set_timeout($fp, 8);
			$res="";
			$n=0;
			while (!feof($fp)) 
			{
				if ($n++ > 4) break;
	  			$res .= fread($fp, 8192);
			}
		 	$info = stream_get_meta_data($fp);
		 	fclose($fp);
		
		 	if ($info['timed_out']) 
			{
				echo 'API: Connection timed out! $NL';
				return -2; // api timeout
		  } else 
			{
				if (strlen($res) > 1000) return -3; // invalid api response (check the API website for possible problems)
				$data=extractBody($res);
				$ar=explode(":",$data);
				if (count($ar) < 4) return -100; // invalid api response
				switch ($ar[0])
				{
					case "ERROR":
						echo "API Error: $res $NL";
						return 0; // Error received
					break;
					case "ROTATE":
						$PROXY['address']=$ar[1];
						$PROXY['port']=$ar[2];
						$PROXY['external_ip']=$ar[3];
						$PROXY['ready']=1;
						usleep(250000); // additional time to avoid connecting during proxy bootup phase, to be 100% sure 1 second needs to be waited
						return 1;
					break;
					default:
						echo "API Error: Received answer $ar[0], expected \"ROTATE\"";
						return -101; // unknown API response
				}
	 		}
	 	} // cmd==rotate
	}
}



function dom2array($node) 
{
  $res = array();
  if($node->nodeType == XML_TEXT_NODE)
  {
  	$res = $node->nodeValue;
  } else
  {
  	if($node->hasAttributes())
  	{
  		$attributes = $node->attributes;
  		if(!is_null($attributes))
  		{
  			$res['@attributes'] = array();
  			foreach ($attributes as $index=>$attr) 
  			{
  				$res['@attributes'][$attr->name] = $attr->value;
  			}
  		}
  	}
  	if($node->hasChildNodes())
  	{
  		$children = $node->childNodes;
  		for($i=0;$i<$children->length;$i++)
  		{
  			$child = $children->item($i);
  			$res[$child->nodeName] = dom2array($child);
  		}
  		$res['textContent']=$node->textContent;
  	}
  }
  return $res;
}


function getContent(&$NodeContent="",$nod)
{    
	$NodList=$nod->childNodes;
	for( $j=0 ;  $j < $NodList->length; $j++ )
	{ 
		$nod2=$NodList->item($j);
		$nodemane=$nod2->nodeName;
		$nodevalue=$nod2->nodeValue;
		if($nod2->nodeType == XML_TEXT_NODE)
		    $NodeContent .= $nodevalue;
		else
		{     $NodeContent .= "<$nodemane ";
		   $attAre=$nod2->attributes;
		   foreach ($attAre as $value)
		      $NodeContent .= "{$value->nodeName}='{$value->nodeValue}'" ;
		    $NodeContent .= ">";                    
		    getContent($NodeContent,$nod2);                    
		    $NodeContent .= "</$nodemane>";
		}
	}
   
}


function dom2array_full($node)
{
    $result = array();
    if($node->nodeType == XML_TEXT_NODE) 
    {
    	$result = $node->nodeValue;
    } else 
    {
    	if($node->hasAttributes()) 
    	{
    		$attributes = $node->attributes;
    		if((!is_null($attributes))&&(count($attributes))) 
    			foreach ($attributes as $index=>$attr) 
    		  	$result[$attr->name] = $attr->value;
    	}
    	if($node->hasChildNodes())
    	{
    		$children = $node->childNodes;
    		for($i=0;$i<$children->length;$i++) 
    		{
    			$child = $children->item($i);
    			if($child->nodeName != '#text')
    			if(!isset($result[$child->nodeName]))
    				$result[$child->nodeName] = dom2array($child);
    			else 
    			{
    				$aux = $result[$child->nodeName];
    				$result[$child->nodeName] = array( $aux );
    				$result[$child->nodeName][] = dom2array($child);
    			}
    		}
    	}
    }
    return $result;
} 


function getip()
{
	global $PROXY;
	if (!$PROXY['ready']) return -1; // proxy not ready
	
	$curl_handle=curl_init();
	curl_setopt($curl_handle,CURLOPT_URL,'http://squabbel.com/ipxx.php'); // this site will return the plain IP address, great for testing if a proxy is ready
	curl_setopt($curl_handle,CURLOPT_CONNECTTIMEOUT,10);
	curl_setopt($curl_handle,CURLOPT_TIMEOUT,10);
	curl_setopt($curl_handle,CURLOPT_RETURNTRANSFER,1);
	$curl_proxy = "$PROXY[address]:$PROXY[port]";
	curl_setopt($curl_handle, CURLOPT_PROXY, $curl_proxy);
	$tested_ip=curl_exec($curl_handle);
	
  if(preg_match("^([1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])(\.([0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5])){3}^", $tested_ip))
  {
  	curl_close($curl_handle);
		return $tested_ip;
	}
  else
  {
  	$info = curl_getinfo($curl_handle);
  	curl_close($curl_handle);
    return 0; // possible error would be a wrong authentication IP or a firewall
  }
}


function new_curl_session($ch=NULL)
{
	global $PROXY;
	if ((!isset($PROXY['ready'])) || (!$PROXY['ready'])) return $ch; // proxy not ready
	
	if (isset($ch) && ($ch != NULL)) 
		curl_close($ch);
  $ch = curl_init();
  curl_setopt ($ch, CURLOPT_HEADER, 0);
  curl_setopt ($ch, CURLOPT_FOLLOWLOCATION, 1);
  curl_setopt ($ch, CURLOPT_RETURNTRANSFER , 1);
  $curl_proxy = "$PROXY[address]:$PROXY[port]";
  curl_setopt($ch, CURLOPT_PROXY, $curl_proxy);
  curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 20);
  curl_setopt($ch, CURLOPT_TIMEOUT, 20);
  curl_setopt($ch, CURLOPT_USERAGENT, "Mozilla/5.0 (Windows; U; Windows NT 5.0; en; rv:1.9.0.4) Gecko/2009011913 Firefox/3.0.6");
	return $ch;
}


function rmkdir($path, $mode = 0755) {
    if (file_exists($path)) return 1;
    return @mkdir($path, $mode);
}


/*
 * For country&language specific searches
 */
function get_google_cc($cc,$lc)
{
	global $pwd;
	global $uid;
	global $PROXY;
	global $LICENSE;
	global $NL;
        global $portal;
	$fp = fsockopen("$portal.seo-proxies.com", 80);
	if (!$fp) 
	{
		echo "Unable to connect to google_cc API $NL";
		return NULL; // connection not possible
	} else 
	{
			fwrite($fp, "GET /g_api.php?api=1&uid=$uid&pwd=$pwd&cmd=google_cc&cc=$cc&lc=$lc HTTP/1.0\r\nHost: $portal.seo-proxies.com\r\nAccept: text/html, text/plain, text/*, */*;q=0.01\r\nAccept-Encoding: plain\r\nAccept-Language: en\r\n\r\n");
			stream_set_timeout($fp, 8);
			$res="";
			$n=0;
			while (!feof($fp)) 
			{
				if ($n++ > 4) break;
	  			$res .= fread($fp, 8192);
			}
		 	$info = stream_get_meta_data($fp);
		 	fclose($fp);
		
		 	if ($info['timed_out']) 
			{
				echo 'API: Connection timed out! $NL';
				return NULL; // api timeout
		  } else 
			{
				$data=extractBody($res);
				$obj=unserialize($data);
				if (isset($obj['error'])) echo $obj['error']."$NL";
				if (isset($obj['info'])) echo $obj['info']."$NL";
				return $obj['data'];
				
				if (strlen($data) < 4) return NULL; // invalid api response
			}
	}
}


?>
