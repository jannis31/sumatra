function draw_raster_plot() {

    var margin = {top: 20, right: 20, bottom: 30, left: 50},
        width = 960 - margin.left - margin.right,
        height = 500 - margin.top - margin.bottom;

    var xScale = d3.scale.linear()
        .domain([0, simtime])
        .range([0, width]);

    var yScale = d3.scale.linear()
        .domain([0, neurons.length])
        .range([0, height]);

    var xAxis = d3.svg.axis()
        .scale(xScale)
        .orient("bottom")
        .ticks(5);

    var yAxis = d3.svg.axis()
        .scale(yScale)
        .orient("left")
        .ticks(5);

    var svg = d3.select("body").append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
      .append("g")
        .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

    svg.append("svg:text")
        .attr("class", "title")
        .attr("x", width/2-margin.left)
        .attr("y", -10)
        .text("Raster plot");

    svg.append("svg:text")
        .attr("class", "x label")
        .attr("text-anchor", "middle")
        .attr("x", width/2)
        .attr("y", height+margin.bottom-12)
        .attr("dy", ".75em")
        .text("Time (ms)");

    svg.append("svg:text")
        .attr("class", "y label")
        .attr("text-anchor", "middle")
        .attr("x", -height/2)
        .attr("y", -(margin.left-5))
        .attr("dy", ".75em")
        .attr("transform", "rotate(-90)")
        .text(neurons.length > 3 ? "Neuron ID": "ID");

    svg.append("g")
        .attr("class", "x axis")
        .attr("transform", "translate(0," + height + ")")
        .call(xAxis);

    svg.append("g")
        .attr("class", "y axis")
        .call(yAxis);

    svg.selectAll("circle")
        .data(data)
      .enter().append("svg:circle")
        .attr("cx", function(d) { return xScale(d[1]); })
        .attr("cy", function(d) { return yScale(d[0]); })
        .attr("r", 1);
}

