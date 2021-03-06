function [ outputInfo ] = compute_Transitiness( info,lppWant,knnGood,nDim,knn,outfile )
%UNTITLED2 Summary of this function goes here
%   Detailed explanation goes here

[ Ymap,Zmap ] = createLPPmap(info, lppWant, nDim, knn);

x=Ymap.mapped(knnGood,:);
y=Ymap.mapped(:,:);

[ dymean, dxmean,dxstd, dxmax ] = knnDistance_inclass( x,y,knn );

%%Write out the results

fid=fopen(outfile,'w');

fprintf(fid,'#Date = %s\n#1SigmaDistance = %f\n#NDim = %i\n#knn = %i\n#type =%s \n',date,dxstd,nDim,knn,info.dettype);
fprintf(fid,'#SvnVersion = %s\n',info.svnVersion);
fprintf(fid,'#TCE    MeanDistance   sampleType\n');

for i=1:length(y)
    
    fprintf(fid,'%s  %f  %i\n', info.tce{i}, dymean(i),info.d(i));
    
end

fclose(fid);


outputInfo=struct([]);
outputInfo(1).Ymap=Ymap;
outputInfo.Zmap=Zmap;
outputInfo.knn=knn;
outputInfo.outfile=outfile;
outputInfo.dymean=dymean;
outputInfo.dxmean=dxmean;
outputInfo.dxstd=dxstd;
outputInfo.dxmax=dxmax;
outputInfo.transitMetric=dymean;
outputInfo.transit1sigmacut=dxstd;
outputInfo.nDim=nDim;
outputInfo.knnGood=knnGood;
outputInfo.lppWant=lppWant;
outputInfo.svnVerrsion='$Id: compute_Transitiness.m 59152 2015-04-27 17:29:22Z smullall $';
oi=catstruct(outputInfo,info);

outputInfo=oi;

end

