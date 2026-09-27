"""Configured coverage regions."""
AREAS = @@AREAS@@

def contains(area,lat,lon):
    return any(s<=lat<n and w<=lon<e for s,n,w,e in area.get('parts',(area['bounds'],)))

def clipped_bounds(area,south,north,west,east):
    rectangles=[]
    for s,n,w,e in area.get('parts',(area['bounds'],)):
        low,high,left,right=max(s,south),min(n,north),max(w,west),min(e,east)
        if low<high and left<right:rectangles.append([[low,left],[high,right]])
    return rectangles
